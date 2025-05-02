import asyncio
import math
import signal
import time
from typing import Dict, Optional

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
from lib.utils.parallel import run_tasks_in_parallel
from tests.orders.helpers import (
    OrderTimingInfo,
    prepare_order_details_statistics,
    prepare_ws_delay_statistics,
    print_cancel_order_stats,
    print_individual_orders_stats,
    print_order_detailed_stats,
    print_ws_stats,
)
from tests.settings import Settings

log = structlog.get_logger(__name__)


@pytest.mark.asyncio
async def test_example_place_order(settings: Settings, rate_limit=4):
    """
    Test placing multiple limit buy orders with rate limiting.

    Args:
        rate_limit (int): Maximum number of orders to submit per second.
                         Adjust this value to control the rate of order submissions.
    """

    web3 = AsyncWeb3(AsyncHTTPProvider(settings.full_rpc_url()))

    client = ClientOrderExecutor(
        web3=web3,
        contract_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        private_key=settings.private_key,
    )
    client.orderbook.set_market_params(await client.orderbook.fetch_market_params())

    ws_order_tester = WsOrderTester(
        market_address=constants.testnet_market_addresses["TEST_CHOG_MON"],
        ws_url=settings.websocket_url,
        rpc_url=settings.full_rpc_url(),
        private_key=settings.private_key,
        client=client,
    )

    try:
        await ws_order_tester.initialize()
    except Exception as e:
        log.error("Error initializing WebSocket tester", error=e)
        log.exception(e)

        assert False

    balance = await web3.eth.get_balance(client.wallet_address)
    log.info("Wallet balance", balance=f"{web3.from_wei(balance, 'ether')} MON")

    price = "0.00000284"
    size = "10000"

    num_orders = 2  # Increased from 1 to get more meaningful statistics

    await add_margin_balance(web3, price, size, num_orders, settings.private_key)

    # Build list of kwargs for each order
    tasks_kwargs = []
    for i in range(num_orders):
        tasks_kwargs.append(
            {
                "web3": web3,
                "client": client,
                "price": price,
                "size": size,
                "cloid": f"mm_{i + 1}",
                "ws_order_tester": ws_order_tester,  # Pass the WebSocket tester to track submission times
            }
        )

    # Track total time for all orders
    start_time_total = time.time()

    log.info("Running orders with rate limit", num_orders=num_orders, rate_limit=rate_limit)
    success_count, fail_count, time_stats = await run_tasks_in_parallel(
        fn=create_limit_buy_order, kwargs_list=tasks_kwargs, rate_limit=rate_limit
    )

    end_time_total = time.time()
    total_duration = end_time_total - start_time_total

    log.info(
        "Order placement complete",
        success_count=success_count,
        fail_count=fail_count,
        total_duration=f"{total_duration:.2f}",
    )

    # Wait for all WebSocket events to be received (with a timeout)
    log.info(
        "Waiting for WebSocket events",
        expected_events=ws_order_tester.expected_events,
        received_events=ws_order_tester.received_events,
    )
    try:
        await asyncio.wait_for(ws_order_tester.all_events_received.wait(), timeout=60)
        log.info("All WebSocket events received", event_count=ws_order_tester.received_events)
    except asyncio.TimeoutError:
        log.warning(
            "Timeout waiting for WebSocket events",
            received=ws_order_tester.received_events,
            expected=ws_order_tester.expected_events,
        )

    print_order_detailed_stats(ws_order_tester.get_order_details())

    print_ws_stats(ws_order_tester.get_delay_statistics())

    print_cancel_order_stats(ws_order_tester.get_cancel_order_stats())

    print_individual_orders_stats(success_count, time_stats, total_duration)

    await ws_order_tester.shutdown(signal.SIGINT)

    assert success_count == num_orders, "Incorrect number of orders placed"


async def create_limit_buy_order(web3, client: ClientOrderExecutor, price, size, cloid, ws_order_tester=None):
    # Start time tracking for order initiation
    start_time = time.time()

    # Use the client extension function to get the next nonce if not provided

    nonce = await get_next_nonce(client)

    market_address = constants.testnet_market_addresses["TEST_CHOG_MON"]

    log.info("Order", cloid=cloid, wallet_address=client.wallet_address)

    order = OrderRequest(
        market_address=market_address,
        order_type="limit",
        side="buy",
        price=price,
        size=size,
        post_only=False,
        cloid=cloid,
    )
    tx_options = TxOptions(nonce=nonce)
    log.info("Placing limit buy order", size=order.size, price=order.price, cloid=cloid)
    tx_hash = await client.place_order(order, tx_options)

    assert tx_hash is not None
    assert len(tx_hash) > 0
    log.info("Limit order transaction sent", tx_hash=tx_hash, cloid=cloid)

    tx_receipt = await web3.eth.wait_for_transaction_receipt(HexStr(tx_hash), timeout=30)
    log.info("Limit order transaction receipt received", tx_receipt=tx_receipt, tx_hash=tx_hash, cloid=cloid)
    assert tx_receipt["status"] == 1, "Order placement failed"

    # End time tracking - this is when the transaction is completed
    end_time = time.time()
    duration = end_time - start_time

    # Record transaction hash, cloid, start time and end time for WebSocket delay tracking
    if ws_order_tester is not None:
        ws_order_tester.add_order_tx(tx_receipt["transactionHash"].hex(), start_time, end_time, cloid)

    log.info(
        "Order placed successfully",
        cloid=cloid,
        block_number=tx_receipt["blockNumber"],
        tx_hash=tx_receipt["transactionHash"].hex(),
        duration=f"{duration:.4f}",
    )

    # Return duration along with cloid for statistics
    return {"cloid": cloid, "duration": duration}


async def cancel_order(client: ClientOrderExecutor, order_id: int):
    cloid = client.order_id_to_cloid[order_id]

    log.info("Cancelling order ...", order_id=order_id, cloid=cloid)

    # Use get_next_nonce function from client_extensions
    nonce = await get_next_nonce(client)
    tx_options = TxOptions(nonce=nonce)

    start_time = time.time()
    tx_hash = await client.cancel_orders(order_ids=[order_id], tx_options=tx_options)
    end_time = time.time()
    duration = end_time - start_time

    assert tx_hash is not None
    assert len(tx_hash) > 0
    log.info("Order cancelled", tx_hash=tx_hash, order_id=order_id, duration=f"{duration:.4f}", cloid=cloid)

    return {
        "cloid": cloid,
        "cancel_duration": duration,
        "cancel_start_time": start_time,
        "cancel_end_time": end_time,
        "cancel_tx_hash": tx_hash,
    }


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
        self.received_events = 0

        # Event to signal when all expected events have been received
        self.all_events_received = asyncio.Event()

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

            assert self.client is not None
            result = await cancel_order(self.client, payload.order_id)

            self.save_order_cancelled_timing_info(result)

            if found:
                self.received_events += 1
                if self.received_events >= self.expected_events:
                    self.all_events_received.set()
        except Exception as e:
            log.error("Error processing on_order_created WebSocket event", error=str(e))
            log.exception(e)
            raise e

    def save_order_cancelled_timing_info(self, result):
        cloid = result["cloid"]
        duration = result["cancel_duration"]
        # Store the cancellation time
        # self.cancel_order_times[cloid] = duration

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
            cloid = order_info.cloid

            # Calculate delays
            start_time = float(order_info.start_time)
            end_time = float(order_info.end_time)

            start_to_end = end_time - start_time
            end_to_ws = receipt_time - end_time
            total_delay = receipt_time - start_time

            self.log.info(
                "WebSocket event timing",
                cloid=cloid,
                tx_hash=order_info.create_tx_hash,
                order_init_to_completion=f"{start_to_end:.4f}",
                order_completion_to_ws=f"{end_to_ws:.4f}",
                total_delay=f"{total_delay:.4f}",
            )

            return True

        return False

    async def on_order_cancelled(self, payload: OrderCancelledPayload):
        # Fix to access order_ids instead of owner property
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

    async def initialize(self):
        self.shutdown_event = asyncio.Future()

        if self.market_address is None or self.rpc_url is None or self.private_key is None or self.ws_url is None:
            raise ValueError("market_address, rpc_url, private_key, and ws_url must be provided")

        self.ws_client = WebSocketHandler(
            websocket_url=self.ws_url,
            market_address=self.market_address,
            market_params=self.client.orderbook.market_params,
            on_order_created=self.on_order_created,
            on_order_cancelled=self.on_order_cancelled,
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
