import asyncio
import math
import signal
import time
import statistics
from typing import Optional, Dict, Any, Union, TypedDict

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


class OrderTimingInfo(TypedDict):
    """Type definition for order timing information"""
    start_time: float
    end_time: float
    cloid: str
    ws_time: float  # Optional in actual usage, but required in TypedDict


@pytest.mark.asyncio
async def test_example_place_order(settings: Settings, rate_limit=14):
    """
    Test placing multiple limit buy orders with rate limiting.

    Args:
        rate_limit (int): Maximum number of orders to submit per second.
                         Adjust this value to control the rate of order submissions.
    """

    web3 = Web3(Web3.HTTPProvider(settings.full_rpc_url()))

    client = ClientOrderExecutor(
        web3=web3,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )

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
            "client": client,
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
    print(f"\nWaiting for WebSocket events to be received. Expected: {ws_order_tester.expected_events} events, Received: {ws_order_tester.received_events} events ...")
    try:
        await asyncio.wait_for(ws_order_tester.all_events_received.wait(), timeout=60)
        print(f"All {ws_order_tester.received_events} WebSocket events received.")
    except asyncio.TimeoutError:
        print(f"Timeout waiting for WebSocket events. Received {ws_order_tester.received_events} of {ws_order_tester.expected_events} expected events.")
    
    # Print detailed order statistics
    print("\n--- Detailed Order Statistics ---")
    print(f"{'CLOID':<10} {'TX Hash':<12} {'Order Init (s)':<15} {'Order Complete (s)':<15} {'WS Event (s)':<15} {'Order Duration (s)':<18} {'WS Delay (s)':<15} {'Total (s)':<10}")
    print("-" * 115)
    
    order_details = ws_order_tester.get_order_details()
    start_reference = min([order["initiation_time"] for order in order_details]) if order_details else 0
    
    for order in order_details:
        # Normalize timestamps relative to the first order
        init_rel = order["initiation_time"] - start_reference
        complete_rel = order["completion_time"] - start_reference
        ws_rel = order["ws_event_time"] - start_reference
        
        print(f"{order['cloid']:<10} {order['tx_hash'][:10]:<12} {init_rel:.4f}{'':>7} {complete_rel:.4f}{'':>7} {ws_rel:.4f}{'':>7} {order['order_execution_duration']:.4f}{'':>10} {order['ws_event_delay']:.4f}{'':>7} {order['total_duration']:.4f}")
    
    # Print WebSocket delay statistics
    ws_stats = ws_order_tester.get_delay_statistics()
    if ws_stats:
        print("\n--- WebSocket Event Delay Statistics ---")
        
        print("\nOrder Execution (Order Initiation to Transaction Completion):")
        print(f"Minimum: {ws_stats['order_to_tx']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['order_to_tx']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['order_to_tx']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['order_to_tx']['median']:.4f} seconds")
        if 'std_dev' in ws_stats['order_to_tx']:
            print(f"Standard deviation: {ws_stats['order_to_tx']['std_dev']:.4f} seconds")
            
        print("\nWebSocket Notification Delay (Transaction Completion to WebSocket Event):")
        print(f"Minimum: {ws_stats['tx_to_ws']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['tx_to_ws']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['tx_to_ws']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['tx_to_ws']['median']:.4f} seconds")
        if 'std_dev' in ws_stats['tx_to_ws']:
            print(f"Standard deviation: {ws_stats['tx_to_ws']['std_dev']:.4f} seconds")
            
        print("\nTotal Delay (Order Initiation to WebSocket Event):")
        print(f"Minimum: {ws_stats['total']['min']:.4f} seconds")
        print(f"Maximum: {ws_stats['total']['max']:.4f} seconds")
        print(f"Mean: {ws_stats['total']['mean']:.4f} seconds")
        print(f"Median: {ws_stats['total']['median']:.4f} seconds")
        if 'std_dev' in ws_stats['total']:
            print(f"Standard deviation: {ws_stats['total']['std_dev']:.4f} seconds")
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

async def create_limit_buy_order(web3, client: ClientOrderExecutor, price, size, cloid, nonce: int, private_key: str, ws_order_tester=None):
    # Start time tracking for order initiation
    start_time = time.time()
    
    market_address = constants.testnet_market_addresses["TEST_CHOG_MON"]

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
    
    # End time tracking - this is when the transaction is completed
    end_time = time.time()
    duration = end_time - start_time
    
    # Record transaction hash, cloid, start time and end time for WebSocket delay tracking
    if ws_order_tester is not None:
        ws_order_tester.add_order_tx(tx_receipt['transactionHash'].hex(), start_time, end_time, cloid)
    
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
        
        # Dictionary to track order times by transaction hash
        self.order_times: Dict[str, Dict[str, Any]] = {}
        
        # Track number of expected and received events
        self.expected_events = 0
        self.received_events = 0
        
        # Event to signal when all expected events have been received
        self.all_events_received = asyncio.Event()

    def add_order_tx(self, tx_hash: str, start_time: float, end_time: float, cloid: str):
        """Record the times for an order by transaction hash"""
        # Normalize tx_hash by removing '0x' prefix if present
        if tx_hash.startswith("0x"):
            tx_hash = tx_hash[2:]
            
        self.order_times[tx_hash] = {
            "start_time": start_time,
            "end_time": end_time,
            "cloid": cloid
        }
        self.expected_events += 1

    async def on_order_created(self, payload: OrderCreatedPayload):
        if payload.owner != self.client.wallet_address:
            return

        # Record the receipt time
        receipt_time = time.time()
        tx_hash = payload.transaction_hash
        
        # Normalize tx_hash by removing '0x' prefix if present
        if tx_hash.startswith("0x"):
            tx_hash = tx_hash[2:]
        
        print(f"WebSocket event: Order created: {payload}")
        
        # Record the WebSocket event time if we have this transaction
        if tx_hash in self.order_times:
            order_info = self.order_times[tx_hash]
            order_info["ws_time"] = receipt_time
            cloid = order_info["cloid"]
            
            # Calculate delays
            start_time = float(order_info["start_time"])
            end_time = float(order_info["end_time"])
            
            start_to_end = end_time - start_time
            end_to_ws = receipt_time - end_time
            total_delay = receipt_time - start_time
            
            print(f"WebSocket event for order '{cloid}' (tx {tx_hash}):")
            print(f"  Order initiation to completion: {start_to_end:.4f} seconds")
            print(f"  Order completion to WebSocket event: {end_to_ws:.4f} seconds")
            print(f"  Total delay (initiation to WebSocket): {total_delay:.4f} seconds")
            
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
        if not self.order_times:
            return None
            
        # Collect delays for orders that have received WebSocket events
        tx_to_ws_delays = []
        order_to_tx_delays = []
        total_delays = []
        
        for tx_hash, times in self.order_times.items():
            if "ws_time" in times:
                start_time = float(times["start_time"])
                end_time = float(times["end_time"])
                ws_time = float(times["ws_time"])
                
                tx_to_ws_delay = ws_time - end_time
                order_to_tx_delay = end_time - start_time 
                total_delay = ws_time - start_time
                
                tx_to_ws_delays.append(tx_to_ws_delay)
                order_to_tx_delays.append(order_to_tx_delay)
                total_delays.append(total_delay)
        
        if not tx_to_ws_delays:
            return None
            
        stats = {
            "count": len(tx_to_ws_delays),
            "tx_to_ws": {
                "min": min(tx_to_ws_delays),
                "max": max(tx_to_ws_delays),
                "mean": statistics.mean(tx_to_ws_delays),
                "median": statistics.median(tx_to_ws_delays)
            },
            "order_to_tx": {
                "min": min(order_to_tx_delays),
                "max": max(order_to_tx_delays),
                "mean": statistics.mean(order_to_tx_delays),
                "median": statistics.median(order_to_tx_delays)
            },
            "total": {
                "min": min(total_delays),
                "max": max(total_delays),
                "mean": statistics.mean(total_delays),
                "median": statistics.median(total_delays)
            }
        }
        
        if len(tx_to_ws_delays) > 1:
            stats["tx_to_ws"]["std_dev"] = statistics.stdev(tx_to_ws_delays)
            stats["order_to_tx"]["std_dev"] = statistics.stdev(order_to_tx_delays)
            stats["total"]["std_dev"] = statistics.stdev(total_delays)
            
        return stats
        
    def get_order_details(self):
        """Get detailed order timing information for each order"""
        result = []
        
        for tx_hash, times in self.order_times.items():
            if "ws_time" in times:
                start_time = float(times["start_time"])
                end_time = float(times["end_time"])
                ws_time = float(times["ws_time"])
                
                record = {
                    "cloid": times["cloid"],
                    "tx_hash": tx_hash,
                    "initiation_time": start_time,
                    "completion_time": end_time,
                    "ws_event_time": ws_time,
                    "order_execution_duration": end_time - start_time,
                    "ws_event_delay": ws_time - end_time,
                    "total_duration": ws_time - start_time
                }
                result.append(record)
        
        return sorted(result, key=lambda x: x["cloid"])




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
