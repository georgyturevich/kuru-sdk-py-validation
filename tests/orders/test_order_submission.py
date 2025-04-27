import asyncio
import math
import signal
import time
import statistics
from typing import Optional, Dict

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

    num_orders = 20  # Increased from 1 to get more meaningful statistics
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
            "ws_order_tester": ws_order_tester,  # Pass the WebSocket tester to track submission times
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
    
    # Wait for all WebSocket events to be received (with a timeout)
    print("\nWaiting for WebSocket events to be received...")
    try:
        await asyncio.wait_for(ws_order_tester.all_events_received.wait(), timeout=60)
        print(f"All {ws_order_tester.received_events} WebSocket events received.")
    except asyncio.TimeoutError:
        print(f"Timeout waiting for WebSocket events. Received {ws_order_tester.received_events} of {ws_order_tester.expected_events} expected events.")
    
    # Print WebSocket delay statistics
    ws_stats = ws_order_tester.get_delay_statistics()
    if ws_stats:
        print("\n--- WebSocket Event Delay Statistics ---")
        print(f"Number of events: {ws_stats['count']}")
        print(f"Minimum delay: {ws_stats['min']:.4f} seconds")
        print(f"Maximum delay: {ws_stats['max']:.4f} seconds")
        print(f"Mean delay: {ws_stats['mean']:.4f} seconds")
        print(f"Median delay: {ws_stats['median']:.4f} seconds")
        if 'std_dev' in ws_stats:
            print(f"Standard deviation: {ws_stats['std_dev']:.4f} seconds")
    else:
        print("\nNo WebSocket event delay statistics available.")
    
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

async def create_limit_buy_order(web3, price, size, cloid, nonce: int, private_key: str, ws_order_tester=None):
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
    
    # Record transaction hash and submission time for WebSocket delay tracking
    if ws_order_tester is not None:
        ws_order_tester.add_order_tx(tx_receipt['transactionHash'].hex(), end_time)
    
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
        
        # Dictionary to track order submission times by transaction hash
        self.tx_submission_times: Dict[str, float] = {}
        
        # Dictionary to track WebSocket event receipt times and delays
        self.ws_event_times: Dict[str, float] = {}
        self.ws_event_delays: Dict[str, float] = {}
        
        # Track number of expected and received events
        self.expected_events = 0
        self.received_events = 0
        
        # Event to signal when all expected events have been received
        self.all_events_received = asyncio.Event()

    def add_order_tx(self, tx_hash: str, submission_time: float):
        """Record the submission time of an order by transaction hash"""
        self.tx_submission_times[tx_hash] = submission_time
        self.expected_events += 1

    async def on_order_created(self, payload: OrderCreatedPayload):
        if payload.owner != self.client.wallet_address:
            return

        # Record the receipt time
        receipt_time = time.time()
        tx_hash = payload.transaction_hash
        if tx_hash.startswith("0x"):
            tx_hash = tx_hash[2:]

        print(f"WebSocket event: Order created: {payload}")
        
        # Calculate and record the delay if we have the submission time
        if tx_hash in self.tx_submission_times:
            submission_time = self.tx_submission_times[tx_hash]
            delay = receipt_time - submission_time
            self.ws_event_times[tx_hash] = receipt_time
            self.ws_event_delays[tx_hash] = delay
            
            print(f"WebSocket delay for tx {tx_hash}: {delay:.4f} seconds")
            
            # Increment received events counter and check if all events received
            self.received_events += 1
            if self.received_events >= self.expected_events:
                self.all_events_received.set()

    async def on_order_cancelled(self, payload: OrderCancelledPayload):
        # Fix to access order_ids instead of owner property
        for order_id in payload.order_ids:
            print(f"WebSocket event: Order cancelled: order_id={order_id}")

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
    
    def get_delay_statistics(self):
        """Calculate statistics about the WebSocket event delays"""
        if not self.ws_event_delays:
            return None
            
        delays = list(self.ws_event_delays.values())
        stats = {
            "count": len(delays),
            "min": min(delays),
            "max": max(delays),
            "mean": statistics.mean(delays),
            "median": statistics.median(delays),
        }
        
        if len(delays) > 1:
            stats["std_dev"] = statistics.stdev(delays)
            
        return stats




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
