import asyncio
import os
import signal

import pytest
from dotenv import load_dotenv
from kuru_sdk import ClientOrderExecutor
from kuru_sdk.types import OrderCreatedPayload, TradePayload, OrderCancelledPayload
from kuru_sdk.websocket_handler import WebSocketHandler
from web3 import Web3

from lib.constants import testnet_market_addresses


@pytest.mark.asyncio
async def test_ws_handler():
    load_dotenv()
    print("Test ws handler")

    ws_order_controller = WsOrderController(
        market_address=testnet_market_addresses["TEST_CHOG_MON"],  # Orderbook address
        ws_url=os.getenv("WEBSOCKET_URL"),  # WebSocket URL
        rpc_url=os.getenv("RPC_URL"),
        private_key=os.getenv("PK2"),
    )

    try:
        await ws_order_controller.initialize()

        await asyncio.sleep(3)

        print("Waiting for information. Press Ctrl+C to exit.")
        await ws_order_controller.shutdown_event  # Wait until shutdown signal is received

    except asyncio.CancelledError:
        print("Main task cancelled.")
    finally:
    # Ensure disconnect is called even if there's an error before shutdown_event is awaited
        if ws_order_controller.shutdown_event and not ws_order_controller.shutdown_event.done():
            print("Performing cleanup due to unexpected exit...")
            # await self.ws_client.disconnect()
            print("Client disconnected.")



class WsOrderController:
    def __init__(self, market_address: str = None, ws_url: str = None, rpc_url: str = None, private_key: str = None):
        self.market_address = market_address
        self.ws_url = ws_url
        self.rpc_url = rpc_url
        self.private_key = private_key

        self.client = None
        self.shutdown_event = None

        self.cloid_to_order = {}
        self.order_id_to_cloid = {}
        self.cloid_status = {}

    def on_order_created(self, payload: OrderCreatedPayload):
        print(f"Order created: {payload}")
        cloid = self.client.order_id_to_cloid[payload.order_id]
        if cloid:
            self.client.cloid_to_order[cloid].size = payload.remaining_size
            self.client.cloid_to_order[cloid].is_cancelled = payload.is_canceled
            if payload.is_canceled:
                self.cloid_status[cloid] = "cancelled"
            elif payload.remaining_size == 0:
                self.cloid_status[cloid] = "filled"
            else:
                self.cloid_status[cloid] = "active"
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            print(self.client.cloid_to_order[cloid])
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")


    def on_trade(self, payload: TradePayload):
        print(f"Trade: {payload}")
        order_id = payload.order_id
        cloid = self.client.order_id_to_cloid[order_id]
        if cloid:
            self.client.cloid_to_order[cloid].size = payload.updated_size
            if payload.updated_size == 0:
                self.cloid_status[cloid] = "filled"
            else:
                self.cloid_status[cloid] = "partially_filled"
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            print(self.client.cloid_to_order[cloid])
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")


    def on_order_cancelled(self, payload: OrderCancelledPayload):
        cloid = 0
        print(f"Order cancelled: {payload}")
        for order_id in payload.order_ids:
            cloid = self.client.order_id_to_cloid[order_id]
            if cloid:
                self.client.cloid_to_order[cloid].is_cancelled = True
                self.cloid_status[cloid] = "cancelled"
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print(self.client.cloid_to_order[cloid])
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

    async def initialize(self):
        self.shutdown_event = asyncio.Future()

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
            on_trade=self.on_trade,
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
            self.shutdown_event.set_result(True)
            # Optional: Clean up signal handlers
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)


