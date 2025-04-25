import os
import math

from dotenv import load_dotenv
import pytest
from eth_typing import HexStr
from eth_utils.currency import from_wei, to_wei
from kuru_sdk import MarginAccount, TxOptions
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest
from web3 import Web3

from lib import constants
from tests.settings import Settings
from tests.utils.parallel import run_tasks_in_parallel

@pytest.mark.asyncio
async def test_example_place_order(settings: Settings, rate_limit=14):
    """
    Test placing multiple limit buy orders with rate limiting.

    Args:
        rate_limit (int): Maximum number of orders to submit per second.
                         Adjust this value to control the rate of order submissions.
    """

    web3 = Web3(Web3.HTTPProvider(settings.full_rpc_url()))

    price = "0.00000284"
    size = "10000"

    num_orders = 1
    await add_margin_balance(web3, price, size, num_orders, settings.private_key)

    # Build list of kwargs for each order
    base_nonce = web3.eth.get_transaction_count(web3.eth.account.from_key(settings.private_key).address)
    tasks_kwargs = []
    for i in range(num_orders):
        tasks_kwargs.append({
            "web3": Web3(Web3.HTTPProvider(settings.full_rpc_url())),
            "price": price,
            "size": size,
            "cloid": f"mm_{i+1}",
            "nonce": base_nonce + i,
            "private_key": settings.private_key,
        })

    print(f"\nRunning {num_orders} orders with rate limit of {rate_limit} orders per second...")
    success_count, fail_count = run_tasks_in_parallel(
        fn=create_limit_buy_order,
        kwargs_list=tasks_kwargs,
        rate_limit=rate_limit,
    )
    print(f"\n{success_count} orders have been placed successfully. {fail_count} orders have failed.")

async def create_limit_buy_order(web3, price, size, cloid, nonce: int, private_key: str):
    market_address = constants.testnet_market_addresses["TEST_CHOG_MON"]
    client = ClientOrderExecutor(
        web3=web3,
        contract_address=market_address,
        private_key=private_key,
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

async def add_margin_balance(web3: Web3, price: str, size: str, num_orders: int, private_key: str):
    margin_account = MarginAccount(
        web3=web3,
        contract_address=constants.testnet_kuru_contract_addresses["margin_account"],
        private_key=private_key
    )

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
async def test_clear_margin_account_balance(settings: Settings):
    load_dotenv()

    web3 = Web3(Web3.HTTPProvider(settings.full_rpc_url()))
    margin_account = MarginAccount(
        web3=web3,
        contract_address=constants.testnet_kuru_contract_addresses["margin_account"],
        private_key=settings.private_key
    )

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
