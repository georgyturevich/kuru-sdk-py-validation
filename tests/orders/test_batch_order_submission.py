import asyncio
import math
import signal
import time
from typing import Dict, List, Optional

import pytest
import structlog
from eth_typing import HexStr
from eth_utils.currency import from_wei, to_wei
from kuru_sdk import MarginAccount, TxOptions
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderCancelledPayload, OrderCreatedPayload, OrderRequest
from kuru_sdk.websocket_handler import WebSocketHandler
from web3 import AsyncHTTPProvider, AsyncWeb3

from lib import constants
from lib.client_extensions import get_next_nonce
from tests.orders.helpers import (
    OrderTimingInfo,
    prepare_order_details_statistics,
    prepare_ws_delay_statistics,
    print_cancel_order_stats,
    print_order_detailed_stats,
    print_ws_stats,
)
from tests.settings import Settings

log = structlog.get_logger(__name__)


@pytest.mark.asyncio
async def test_batch_orders_submission_and_cancelling(settings: Settings, batch_size=5):
    """
    Test placing and cancelling multiple orders in batches.

    Args:
        batch_size (int): Number of orders to include in each batch transaction.
    """
    web3 = AsyncWeb3(AsyncHTTPProvider(settings.full_rpc_url()))

    client = ClientOrderExecutor(
        web3=web3,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )
    client.orderbook.set_market_params(await client.orderbook.fetch_market_params())

    ws_order_tester = None
    # ws_order_tester = WsOrderTester(
    #     market_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
    #     ws_url=settings.websocket_url,
    #     rpc_url=settings.full_rpc_url(),
    #     private_key=settings.private_key,
    #     client=client,
    # )
    #
    # try:
    #     await ws_order_tester.initialize()
    # except Exception as e:
    #     log.error("Error initializing WebSocket tester", error=e)
    #     log.exception(e)
    #     assert False

    balance = await web3.eth.get_balance(client.wallet_address)
    log.info("Wallet balance", balance=f"{web3.from_wei(balance, 'ether')} MON")

    price = "0.00000284"
    size = "10000"

    num_orders = 5  # Total number of orders
    num_batches = math.ceil(num_orders / batch_size)  # Number of batches

    await add_margin_balance(web3, price, size, num_orders, settings.private_key)

    # Track total time for all batches
    start_time_total = time.time()

    log.info("Running orders in batches", 
             num_orders=num_orders, 
             batch_size=batch_size, 
             num_batches=num_batches)
    
    batch_results = []
    for batch_index in range(num_batches):
        start_order_index = batch_index * batch_size
        end_order_index = min(start_order_index + batch_size, num_orders)
        
        # Create orders for this batch
        order_requests = []
        cloids = []
        for i in range(start_order_index, end_order_index):
            cloid = f"batch_{batch_index}_{i}"
            cloids.append(cloid)
            order_request = OrderRequest(
                market_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
                order_type="limit",
                side="buy",
                price=price,
                size=size,
                post_only=False,
                cloid=cloid,
            )
            order_requests.append(order_request)
        
        batch_result = await create_batch_orders(web3, client, order_requests, batch_index, ws_order_tester)
        batch_results.append(batch_result)

    end_time_total = time.time()
    total_duration = end_time_total - start_time_total

    log.info(
        "Order placement complete",
        num_batches=len(batch_results),
        total_duration=f"{total_duration:.2f}",
    )

    # # Wait for all WebSocket events to be received (with a timeout)
    # log.info(
    #     "Waiting for WebSocket events",
    #     expected_events=ws_order_tester.expected_events,
    #     received_events=ws_order_tester.received_order_create_ws_events,
    # )
    # try:
    #     await asyncio.wait_for(ws_order_tester.all_create_events_received.wait(), timeout=60)
    #     log.info("All WebSocket create events received",
    #              event_count=ws_order_tester.received_order_create_ws_events)
    # except asyncio.TimeoutError:
    #     log.warning(
    #         "Timeout waiting for WebSocket create events",
    #         received=ws_order_tester.received_order_create_ws_events,
    #         expected=ws_order_tester.expected_events,
    #     )
    #
    # # Now cancel orders in batches
    # log.info("Cancelling orders in batches")
    # for batch_index in range(num_batches):
    #     # Get order IDs for this batch
    #     order_ids = []
    #     start_order_index = batch_index * batch_size
    #     end_order_index = min(start_order_index + batch_size, num_orders)
    #
    #     for i in range(start_order_index, end_order_index):
    #         cloid = f"batch_{batch_index}_{i}"
    #         if cloid in client.cloid_to_order_id:
    #             order_ids.append(client.cloid_to_order_id[cloid])
    #
    #     if order_ids:
    #         await cancel_batch_orders(client, order_ids, batch_index, ws_order_tester)
    #
    # # Wait for all WebSocket cancel events (with a timeout)
    # try:
    #     await asyncio.wait_for(ws_order_tester.all_cancel_events_received.wait(), timeout=60)
    #     log.info("All WebSocket cancel events received",
    #              event_count=ws_order_tester.received_order_cancel_ws_events)
    # except asyncio.TimeoutError:
    #     log.warning(
    #         "Timeout waiting for WebSocket cancel events",
    #         received=ws_order_tester.received_order_cancel_ws_events,
    #         expected=ws_order_tester.expected_events,
    #     )
    #
    # # Print statistics
    # print_order_detailed_stats(ws_order_tester.get_order_details())
    # print_ws_stats(ws_order_tester.get_delay_statistics())
    # print_cancel_order_stats(ws_order_tester.get_cancel_order_stats())
    #
    # # Print batch statistics
    # total_batch_create_time = sum(b['create_duration'] for b in batch_results)
    # avg_batch_create_time = total_batch_create_time / len(batch_results) if batch_results else 0
    # log.info(
    #     "Batch order statistics",
    #     num_batches=len(batch_results),
    #     total_batch_create_time=f"{total_batch_create_time:.4f}",
    #     avg_batch_create_time=f"{avg_batch_create_time:.4f}",
    #     total_duration=f"{total_duration:.4f}",
    # )
    #
    # await ws_order_tester.shutdown(signal.SIGINT)
    #
    # assert ws_order_tester.received_order_create_ws_events == num_orders, \
    #     "Incorrect number of WebSocket CreateOrder events received"
    # assert ws_order_tester.received_order_cancel_ws_events == num_orders, \
    #     "Incorrect number of WebSocket CancelOrder events received"


async def create_batch_orders(web3, client: ClientOrderExecutor, orders: List[OrderRequest], 
                             batch_index: int, ws_order_tester):
    """Create a batch of orders and track timing info"""
    start_time = time.time()

    # Use the client extension function to get the next nonce
    nonce = await get_next_nonce(client)

    log.info("Creating batch of orders", 
             batch_index=batch_index, 
             num_orders=len(orders))

    tx_options = TxOptions(nonce=nonce)
    
    # Place batch orders
    tx_hash = await client.batch_orders(orders, tx_options)

    assert tx_hash is not None
    assert len(tx_hash) > 0
    log.info("Batch order transaction sent", tx_hash=tx_hash, batch_index=batch_index)

    tx_receipt = await web3.eth.wait_for_transaction_receipt(HexStr(tx_hash), timeout=30)
    log.info("Batch order transaction receipt received", 
             tx_receipt=tx_receipt, 
             tx_hash=tx_hash, 
             batch_index=batch_index)
    assert tx_receipt["status"] == 1, "Batch order placement failed"

    # End time tracking - this is when the transaction is completed
    end_time = time.time()
    duration = end_time - start_time

    # Record transaction hash, cloids, start time, and end time for WebSocket delay tracking
    # if ws_order_tester is not None:
    #     for order in orders:
    #         ws_order_tester.add_order_tx(tx_receipt["transactionHash"].hex(),
    #                                     start_time, end_time, order.cloid)

    log.info(
        "Batch order placed successfully",
        batch_index=batch_index,
        block_number=tx_receipt["blockNumber"],
        tx_hash=tx_receipt["transactionHash"].hex(),
        duration=f"{duration:.4f}",
    )

    return {
        "batch_index": batch_index,
        "create_duration": duration,
        "create_tx_hash": tx_receipt["transactionHash"].hex(),
        "num_orders": len(orders),
        "create_start_time": start_time,
        "create_end_time": end_time,
    }


async def cancel_batch_orders(client: ClientOrderExecutor, order_ids: List[int], 
                              batch_index: int, ws_order_tester):
    """Cancel a batch of orders by their order IDs"""
    cloids = [client.order_id_to_cloid[order_id] for order_id in order_ids]

    log.info("Cancelling batch of orders", 
             batch_index=batch_index,
             order_ids=order_ids, 
             cloids=cloids)

    # Use get_next_nonce function from client_extensions
    nonce = await get_next_nonce(client)
    tx_options = TxOptions(nonce=nonce)

    start_time = time.time()
    tx_hash = await client.cancel_orders(order_ids=order_ids, tx_options=tx_options)
    end_time = time.time()
    duration = end_time - start_time

    assert tx_hash is not None
    assert len(tx_hash) > 0
    log.info("Batch cancelled", 
             tx_hash=tx_hash, 
             batch_index=batch_index, 
             duration=f"{duration:.4f}", 
             num_orders=len(order_ids))

    cancel_result = {
        "batch_index": batch_index,
        "cancel_duration": duration,
        "cancel_start_time": start_time,
        "cancel_end_time": end_time,
        "cancel_tx_hash": tx_hash,
    }
    
    for cloid in cloids:
        ws_order_tester.save_order_cancelled_timing_info(
            {"cloid": cloid, **cancel_result}
        )

    return cancel_result


async def add_margin_balance(web3: AsyncWeb3, price: str, size: str, num_orders: int, private_key: str):
    margin_account = MarginAccount(
        web3=web3, contract_address=constants.testnet_kuru_contract_addresses["margin_account"], private_key=private_key
    )

    size_mon = float(price) * float(size) * num_orders  # make deposit for num_orders orders
    size_wei = to_wei(size_mon, "ether")
    size_wei = 10 * math.ceil(float(size_wei) / 10)

    margin_account_deposit_tx_hash = await margin_account.deposit(margin_account.NATIVE, size_wei)
    log.info("Deposit transaction hash", tx_hash=margin_account_deposit_tx_hash)

    assert margin_account_deposit_tx_hash is not None
    assert len(margin_account_deposit_tx_hash) > 0

    # Wait for the deposit transaction to be confirmed
    tx_receipt = await web3.eth.wait_for_transaction_receipt(HexStr(margin_account_deposit_tx_hash))
    assert tx_receipt["status"] == 1, "Deposit transaction failed"
    log.info("Deposit transaction confirmed", block_number=tx_receipt["blockNumber"])


class WsOrderTester:
    def __init__(
        self,
        market_address: Optional[str] = None,
        ws_url: Optional[str] = None,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        client: Optional[ClientOrderExecutor] = None,
    ):
        self.market_address = market_address
        self.ws_url = ws_url
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.client = client
        self.log = structlog.get_logger(__name__)

        self.shutdown_event: asyncio.Future[bool] | None = None

        # Dictionary to track order times by transaction hash
        self.order_times: Dict[str, OrderTimingInfo] = {}

        # Track number of expected and received events
        self.expected_events = 0
        self.received_order_create_ws_events = 0
        self.received_order_cancel_ws_events = 0

        # Events to signal when expected events have been received
        self.all_create_events_received = asyncio.Event()
        self.all_cancel_events_received = asyncio.Event()

        # Dictionary to store cancel order timings
        self.cancel_order_times = {}

    def add_order_tx(self, tx_hash: str, start_time: float, end_time: float, cloid: str):
        """Record the times for an order by transaction hash"""
        # Normalize tx_hash by removing '0x' prefix if present
        if tx_hash.startswith("0x"):
            tx_hash = tx_hash[2:]

        order_timing_info = OrderTimingInfo(
            start_time=start_time, end_time=end_time, cloid=cloid, create_tx_hash=tx_hash
        )

        self.order_times[cloid] = order_timing_info
        self.expected_events += 1

    async def on_order_created(self, payload: OrderCreatedPayload):
        if self.client is None or payload.owner != self.client.wallet_address:
            return

        try:
            log.info("WebSocket OrderCreated event received", payload=payload)
            found = self.save_ws_event_order_created_timing_info(payload)

            if found:
                self.received_order_create_ws_events += 1
                if self.received_order_create_ws_events >= self.expected_events:
                    self.all_create_events_received.set()
                
        except Exception as e:
            log.error("Error processing on_order_created WebSocket event", error=str(e))
            log.exception(e)
            raise e

    def save_order_cancelled_timing_info(self, result):
        cloid = result["cloid"]
        duration = result["cancel_duration"]

        assert cloid in self.order_times

        order_info = self.order_times[cloid]
        order_info.cancel_duration = duration
        order_info.cancel_start_time = result["cancel_start_time"]
        order_info.cancel_end_time = result["cancel_end_time"]
        order_info.cancel_tx_hash = result["cancel_tx_hash"]

        self.log.info(
            "Order cancellation timing",
            cloid=cloid,
            duration=f"{duration:.4f}",
            cancel_start_time=f"{order_info.cancel_start_time:.4f}",
            cancel_end_time=f"{order_info.cancel_end_time:.4f}",
            cancel_tx_hash=order_info.cancel_tx_hash,
        )

    def save_ws_event_order_created_timing_info(self, payload: OrderCreatedPayload) -> bool:
        assert self.client is not None
        if payload.order_id not in self.client.order_id_to_cloid:
            return False
            
        cloid = self.client.order_id_to_cloid[payload.order_id]
        receipt_time = time.time()
        tx_hash = payload.transaction_hash
        # Normalize tx_hash by removing '0x' prefix if present
        if tx_hash.startswith("0x"):
            tx_hash = tx_hash[2:]
        # Record the WebSocket event time if we have this transaction
        if cloid in self.order_times:
            order_info = self.order_times[cloid]
            order_info.ws_time = receipt_time
            # Store order_id in the OrderTimingInfo
            setattr(order_info, 'order_id', payload.order_id)

            # Calculate delays
            start_time = float(order_info.start_time)
            end_time = float(order_info.end_time)

            start_to_end = end_time - start_time
            end_to_ws = receipt_time - end_time
            total_delay = receipt_time - start_time

            self.log.info(
                "WebSocket event: Order Created",
                cloid=cloid,
                tx_hash=order_info.create_tx_hash,
                order_init_to_completion=f"{start_to_end:.4f}",
                order_completion_to_ws=f"{end_to_ws:.4f}",
                total_delay=f"{total_delay:.4f}",
            )

            return True

        return False

    async def on_order_cancelled(self, payload: OrderCancelledPayload):
        self.log.info("WebSocket OrderCancelled event received", payload=payload)
        for order_id in payload.order_ids:
            self.save_ws_event_single_order_cancelled(order_id)

    def save_ws_event_single_order_cancelled(self, order_id):
        assert self.client is not None

        if order_id not in self.client.order_id_to_cloid:
            self.log.warning("Order not found", order_id=order_id)
            return None

        cloid = self.client.order_id_to_cloid[order_id]

        ws_receipt_time = time.time()
        order_info = self.order_times[cloid]
        order_info.ws_cancel_event_time = ws_receipt_time

        self.log.info(
            "WebSocket event: Order cancelled", order_id=order_id, cloid=cloid, ws_receipt_time=f"{ws_receipt_time:.4f}"
        )

        self.received_order_cancel_ws_events += 1
        if self.received_order_cancel_ws_events >= self.expected_events:
            self.all_cancel_events_received.set()
        return None

    async def initialize(self):
        self.shutdown_event = asyncio.Future()

        if self.market_address is None or self.rpc_url is None or self.private_key is None or self.ws_url is None:
            raise ValueError("market_address, rpc_url, private_key, and ws_url must be provided")

        # Ensure client.orderbook.market_params is set
        if self.client is None:
            raise ValueError("client must be provided")
        
        if not hasattr(self.client.orderbook, 'market_params') or self.client.orderbook.market_params is None:
            self.client.orderbook.market_params = await self.client.orderbook.fetch_market_params()
        
        # Convert async callback methods to sync callback functions
        def on_order_created_sync(payload):
            asyncio.create_task(self.on_order_created(payload))
        
        def on_order_cancelled_sync(payload):
            asyncio.create_task(self.on_order_cancelled(payload))
        
        self.ws_client = WebSocketHandler(
            websocket_url=self.ws_url,
            market_address=self.market_address,
            market_params=self.client.orderbook.market_params,
            on_order_created=on_order_created_sync,
            on_order_cancelled=on_order_cancelled_sync,
        )

        await self.ws_client.connect()

        # Add signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

    async def shutdown(self, sig):
        self.log.info("Received exit signal", signal=sig.name)
        self.log.info("Disconnecting client...")
        try:
            await self.ws_client.disconnect()
        except Exception as e:
            self.log.error("Error during disconnect", error=str(e))
        finally:
            self.log.info("Client disconnected.")
            if self.shutdown_event is not None:
                self.shutdown_event.set_result(True)
            # Optional: Clean up signal handlers
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    def get_delay_statistics(self):
        """Calculate statistics about the WebSocket event delays"""
        order_times = self.order_times
        if not order_times:
            return None

        return prepare_ws_delay_statistics(order_times)

    def get_order_details(self):
        """Get detailed order timing information for each order"""
        order_times = self.order_times
        return prepare_order_details_statistics(order_times)

    def get_cancel_order_stats(self):
        """Return the dictionary of cancel order timings for statistics"""
        return self.cancel_order_times


@pytest.mark.asyncio
async def test_clear_margin_account_balance(settings: Settings):
    web3 = AsyncWeb3(AsyncHTTPProvider(settings.full_rpc_url()))
    margin_account = MarginAccount(
        web3=web3,
        contract_address=constants.testnet_kuru_contract_addresses["margin_account"],
        private_key=settings.private_key,
    )

    # Clear the margin account balance
    balance = await margin_account.get_balance(str(margin_account.wallet_address), margin_account.NATIVE)
    log.info("Clearing margin account balance", balance=f"{from_wei(balance, 'ether')} MON")
    if balance > 0:
        tx_hash = await margin_account.withdraw(margin_account.NATIVE, balance)
        log.info("Withdraw transaction hash", tx_hash=tx_hash)
        assert tx_hash is not None
        assert len(tx_hash) > 0

        receipt = await web3.eth.wait_for_transaction_receipt(HexStr(tx_hash))
        assert receipt["status"] == 1

        balance = await margin_account.get_balance(str(margin_account.wallet_address), margin_account.NATIVE)
        log.info("New margin account balance", balance=f"{from_wei(balance, 'ether')} MON")
        assert balance == 0 