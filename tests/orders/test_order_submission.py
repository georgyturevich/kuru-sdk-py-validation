import os
import asyncio
import concurrent.futures
import math
import time

from Crypto.Util import number
from dotenv import load_dotenv
import pytest
from eth_typing import HexStr
from eth_utils.currency import from_wei, to_wei
from kuru_sdk import MarginAccount, TxOptions
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest
from pyrate_limiter import Duration, Rate, Limiter
from web3 import Web3

@pytest.mark.asyncio
async def test_example_place_order(rate_limit=14):
    """
    Test placing multiple limit buy orders with rate limiting.

    Args:
        rate_limit (int): Maximum number of orders to submit per second. Default is 5.
                         Adjust this value to control the rate of order submissions.
    """
    load_dotenv()

    web3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))

    price = "0.00000284"
    size = "10000"

    num_orders = 20
    await add_margin_balance(web3, price, size, num_orders)

    # Define a wrapper function to run async function in executor
    def run_order_in_thread(web3_provider_url, price, size, cloid, nonce: number, limiter: Limiter):
        limit_result = limiter.try_acquire("order_submission")

        print(f"{time.strftime("%H:%M:%S", time.localtime())} Order submission rate limit result: {limit_result}")

        # Create a new Web3 instance for each thread to avoid potential thread-safety issues
        thread_web3 = Web3(Web3.HTTPProvider(web3_provider_url))

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the async function in this thread's event loop
            return loop.run_until_complete(create_limit_buy_order(thread_web3, price, size, cloid, nonce))
        finally:
            loop.close()

    # Run tasks in parallel using ThreadPoolExecutor with rate limiting using pyrate-limiter
    print(f"\nRunning {num_orders} orders with rate limit of {rate_limit} orders per second...")
    futures = {}
    web3_provider_url = os.getenv("RPC_URL")
    success_count = 0
    fail_count = 0

    # Create a rate limiter with the specified rate limit
    rate = Rate(limit=rate_limit, interval=Duration.SECOND)
    limiter = Limiter(rate, raise_when_fail=False, max_delay=2*Duration.SECOND)

    nonce = web3.eth.get_transaction_count(web3.eth.account.from_key(os.getenv("PRIVATE_KEY")).address)

    with concurrent.futures.ThreadPoolExecutor(max_workers=rate_limit) as executor:
        # Submit all orders with rate limiting
        all_futures = {}

        for i in range(num_orders):
            cloid = f"mm_{i+1}"

            # current time in humand-readable format
            current_time = time.strftime("%H:%M:%S", time.localtime())
            print(f"{current_time} Submitting order {i+1}/{num_orders} with cloid {cloid} -  ...")
            future = executor.submit(run_order_in_thread, web3_provider_url, price, size, cloid, nonce, limiter)
            nonce = nonce + 1
            all_futures[future] = cloid
            futures[future] = cloid

        # Wait for all orders to complete
        for future in concurrent.futures.as_completed(all_futures.keys()):
            cloid = all_futures[future]
            try:
                future.result()
                success_count += 1
                print(f"Order execution for cloid {cloid} completed successfully.")
            except Exception as exc:
                fail_count += 1
                print(f"Order execution for cloid {cloid} generated an exception: {exc}")


    print(f"\n{success_count} orders have been placed successfully. {fail_count} orders have failed.")

async def create_limit_buy_order(web3, price, size, cloid, nonce: number):
    market_address = "0x05e6f736b5dedd60693fa806ce353156a1b73cf3" #// CHOG-MON https://www.kuru.io/trade/0x05e6f736b5dedd60693fa806ce353156a1b73cf3
    client = ClientOrderExecutor(
        web3=web3,
        contract_address=market_address,
        private_key=os.getenv("PRIVATE_KEY"),
    )

    print(f"\nOrder {cloid}:")
    print(f"Wallet address: {client.wallet_address}")

    balance = web3.eth.get_balance(client.wallet_address)
    print(f"Wallet balance: {web3.from_wei(balance, 'ether')} MON")

    order = OrderRequest(
        market_address=market_address,
        order_type='limit',
        side='buy',
        price=price,
        size=size,
        post_only=False,
        cloid=cloid
    )
    tx_options = TxOptions(nonce=nonce)
    print(f"Placing limit buy order: {order.size} units at {order.price} with cloid {cloid}")
    tx_hash = await client.place_order(order, tx_options)

    assert tx_hash is not None
    assert len(tx_hash) > 0

    tx_receipt = web3.eth.wait_for_transaction_receipt(HexStr(tx_hash))
    assert tx_receipt['status'] == 1, "Order placement failed"
    print(f"Order '{cloid}' placed successfully. Block number: {tx_receipt['blockNumber']}, Tx hash: {tx_receipt['transactionHash'].hex()}")

async def add_margin_balance(web3: Web3, price: str, size: str, num_orders: int):
    margin_account = MarginAccount(web3=web3, contract_address="0x4B186949F31FCA0aD08497Df9169a6bEbF0e26ef", private_key=os.getenv("PRIVATE_KEY"))

    size_mon = float(price) * float(size) * num_orders # make deposit for num_orders orders
    size_wei = to_wei(size_mon, "ether")
    size_wei = 10 * math.ceil(float(size_wei) / 10)

    margin_account_deposit_tx_hash = await margin_account.deposit(margin_account.NATIVE, size_wei)
    print(f"Deposit transaction hash: {margin_account_deposit_tx_hash}")

    assert margin_account_deposit_tx_hash is not None
    assert len(margin_account_deposit_tx_hash) > 0

    # Wait for the deposit transaction to be confirmed
    tx_receipt = web3.eth.wait_for_transaction_receipt(HexStr(margin_account_deposit_tx_hash))
    assert tx_receipt['status'] == 1, "Deposit transaction failed"
    print(f"Deposit transaction confirmed in block {tx_receipt['blockNumber']}")

@pytest.mark.asyncio
async def test_clear_margin_account_balance():
    load_dotenv()

    web3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
    margin_account = MarginAccount(web3=web3, contract_address="0x4B186949F31FCA0aD08497Df9169a6bEbF0e26ef", private_key=os.getenv("PRIVATE_KEY"))

    # Clear the margin account balance
    balance = await margin_account.get_balance(margin_account.wallet_address, margin_account.NATIVE)
    print(f"Clearing margin account balance: {from_wei(balance, "ether")} MON")
    if balance > 0:
        tx_hash = await margin_account.withdraw(margin_account.NATIVE, balance)
        print(f"Withdraw transaction hash: {tx_hash}")
        assert tx_hash is not None
        assert len(tx_hash) > 0

        receipt = web3.eth.wait_for_transaction_receipt(HexStr(tx_hash))
        assert receipt["status"] == 1

        balance = await margin_account.get_balance(margin_account.wallet_address, margin_account.NATIVE)
        print(f"New margin account balance: {from_wei(balance, "ether")} MON")
        assert balance == 0
