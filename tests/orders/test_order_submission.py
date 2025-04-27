import asyncio
import math
import signal
import time
import statistics
from typing import Optional

from dotenv import load_dotenv
import pytest
from eth_typing import HexStr
from eth_utils.currency import from_wei, to_wei
from kuru_sdk import MarginAccount, TxOptions
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest, OrderCreatedPayload, OrderCancelledPayload
from kuru_sdk.websocket_handler import WebSocketHandler
from web3 import Web3

from lib import constants
from tests.settings import Settings
from lib.utils.parallel import run_tasks_in_parallel

@pytest.mark.asyncio
async def test_example_place_order(settings: Settings, rate_limit=14):
    """
    Test placing multiple limit buy orders with rate limiting.

    Args:
        rate_limit (int): Maximum number of orders to submit per second.
                         Adjust this value to control the rate of order submissions.
    """

    web3 = Web3(Web3.HTTPProvider(settings.full_rpc_url()))


    ws_order_tester = WsOrderTester(
        market_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        ws_url=settings.websocket_url,
        rpc_url=settings.full_rpc_url(),
        private_key=settings.private_key
    )
    await ws_order_tester.initialize()

    price = "0.00000284"
    size = "10000"

    num_orders = 1  # Increased from 1 to get more meaningful statistics
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

    # Track total time for all orders
    start_time_total = time.time()
    
    print(f"\nRunning {num_orders} orders with rate limit of {rate_limit} orders per second...")
    success_count, fail_count, time_stats = run_tasks_in_parallel(
        fn=create_limit_buy_order,
        kwargs_list=tasks_kwargs,
        rate_limit=rate_limit,
    )
    
    end_time_total = time.time()
    total_duration = end_time_total - start_time_total
    
    print(f"\n{success_count} orders have been placed successfully. {fail_count} orders have failed.")
    print(f"Total time for all orders: {total_duration:.2f} seconds")
    
    await asyncio.sleep(5)
    await ws_order_tester.shutdown(signal.SIGINT)
    
    # Print detailed time statistics for individual orders
    if time_stats:
        print("\n--- Time Statistics ---")
        print(f"{'Order':<10} {'Duration (s)':<15}")
        print("-" * 25)
        
        durations = list(time_stats.values())
        for cloid, duration in sorted(time_stats.items()):
            print(f"{cloid:<10} {duration:.4f}")
        
        if success_count > 0:
            print("\n--- Summary Statistics ---")
            avg_time = sum(durations) / len(durations)
            print(f"Average time: {avg_time:.4f} seconds")
            
            if len(durations) > 1:
                min_time = min(durations)
                max_time = max(durations)
                median_time = statistics.median(durations)
                std_dev = statistics.stdev(durations) if len(durations) > 1 else 0
                
                print(f"Min time: {min_time:.4f} seconds")
                print(f"Max time: {max_time:.4f} seconds")
                print(f"Median time: {median_time:.4f} seconds")
                print(f"Standard deviation: {std_dev:.4f} seconds")
                
            print(f"Total throughput: {success_count / total_duration:.2f} orders/second")

async def create_limit_buy_order(web3, price, size, cloid, nonce: int, private_key: str):
    # Start time tracking
    start_time = time.time()
    
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
    
    # End time tracking
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Order '{cloid}' placed successfully. Block number: {tx_receipt['blockNumber']}, Tx hash: {tx_receipt['transactionHash'].hex()}")
    print(f"Time taken for order '{cloid}': {duration:.4f} seconds")
    
    # Return duration along with cloid for statistics
    return {"cloid": cloid, "duration": duration}

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


class WsOrderTester:
    def __init__(self, market_address: Optional[str] = None, ws_url: Optional[str] = None, rpc_url: Optional[str] = None, private_key: Optional[str] = None):
        self.market_address = market_address
        self.ws_url = ws_url
        self.rpc_url = rpc_url
        self.private_key = private_key

        self.shutdown_event: asyncio.Future[bool] | None = None

    def on_order_created(self, payload: OrderCreatedPayload):
        if payload.owner != self.client.wallet_address:
            return

        print(f"WebSocket even: Order created: {payload}")

    def on_order_cancelled(self, payload: OrderCancelledPayload):
        if payload.owner != self.client.wallet_address:
            return

        print(f"WebSocket even: Order cancelled: {payload}")

    async def initialize(self):
        self.shutdown_event = asyncio.Future()

        if self.market_address is None or self.rpc_url is None or self.private_key is None or self.ws_url is None:
            raise ValueError("market_address, rpc_url, private_key, and ws_url must be provided")

        self.client = ClientOrderExecutor(
            web3=Web3(Web3.HTTPProvider(self.rpc_url)),
            contract_address=self.market_address,
            private_key=self.private_key,
        )

        self.ws_client = WebSocketHandler(
            websocket_url=self.ws_url,
            market_address=self.market_address,
            market_params=self.client.orderbook.market_params,
            on_order_created=self.on_order_created,
            on_order_cancelled=self.on_order_cancelled
        )

        await self.ws_client.connect()

        # Add signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

    async def shutdown(self, sig):
        print(f"\nReceived exit signal {sig.name}...")
        print("Disconnecting client...")
        try:
            await self.ws_client.disconnect()
        except Exception as e:
            print(f"Error during disconnect: {e}")
        finally:
            print("Client disconnected.")
            if self.shutdown_event is not None:
                self.shutdown_event.set_result(True)
            # Optional: Clean up signal handlers
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)




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
