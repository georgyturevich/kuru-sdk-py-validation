import json
import os
from typing import TypedDict, Optional, List
from datetime import datetime, timezone

from dotenv import load_dotenv
import pytest
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest, Order as LibraryOrder
from web3 import Web3
from pydantic import BaseModel, Field, ValidationError, field_validator


ADDRESSES = {
    'orderbook': '0x05e6f736b5dedd60693fa806ce353156a1b73cf3',
}

class MarketAddresses(TypedDict):
    MON_USDC: str
    DAK_MON: str
    CHOG_MON: str
    YAKI_MON: str
    KB_MON: str

testnet_market_addresses: MarketAddresses = {
    "MON_USDC": "0xd3af145f1aa1a471b5f0f62c52cf8fcdc9ab55d3",
    "DAK_MON": "0x94b72620e65577de5fb2b8a8b93328caff6ca161b",
    "CHOG_MON": "0x277bf4a0aac16f19d7bf592feffc8d2d9a890508",
    "YAKI_MON": "0xd5c1dc181c359f0199c83045a85cd2556b325de0",
    "KB_MON": "0x37676650654c9c2c36fcecfaea6172ee1849f9a4",
}

# --- Define Local Pydantic Model for API Response Parsing ---
class ParsedOrder(BaseModel):
    """Local Pydantic model to parse the structure from the API response."""
    market_address: str = Field(..., alias='marketAddress')
    order_id: Optional[int] = Field(None, alias='orderid')
    owner: str
    size: str
    price: str
    is_buy: bool = Field(..., alias='isbuy')
    remaining_size: str = Field(..., alias='remainingsize')
    is_canceled: bool = Field(..., alias='iscanceled')
    block_number: Optional[str] = Field(None, alias='blocknumber')
    tx_index: Optional[str] = Field(None, alias='txindex')
    log_index: Optional[str] = Field(None, alias='logindex')
    transaction_hash: Optional[str] = Field(None, alias='transactionhash')
    trigger_time: Optional[datetime] = Field(None, alias='triggertime')
    total_size: str = Field(..., alias='total_size')

    @field_validator('order_id', mode='before')
    @classmethod
    def validate_order_id(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            print(f"Warning: Could not parse orderid: {v}. Setting to None.")
            return None

    class Config:
        populate_by_name = True
        extra = 'ignore'
# --- End Local Pydantic Model Definition ---


@pytest.mark.asyncio
async def test_limit_order_submission():

    load_dotenv()

    market_orderbook_addr = ADDRESSES['orderbook']

    client = ClientOrderExecutor(
        web3=Web3(Web3.HTTPProvider(os.getenv("RPC_URL"))),
        contract_address=market_orderbook_addr,
        private_key=os.getenv("PK"),
    )

    # Create an order
    
    order = OrderRequest(
        market_address=market_orderbook_addr,
        order_type='limit',
        side='buy',
        price=0.0000002,
        size=10000,
        cloid="test_order_1"
    )

    # Submit order
    tx_hash = await client.place_order(order)

    # Verify tx_hash exists
    assert tx_hash is not None
    assert len(tx_hash) > 0

    print(tx_hash)
    
@pytest.mark.asyncio
async def test_get_order_history():

    load_dotenv()

    market_orderbook_addr = ADDRESSES['orderbook']

    client = ClientOrderExecutor(
        web3=Web3(Web3.HTTPProvider(os.getenv("RPC_URL"))),
        contract_address=market_orderbook_addr,
        private_key=os.getenv("PK"),
        kuru_api_url=os.getenv("KURU_API_URL")
    )

    #
    #
    # Print orderbook details in a readable format
    print("\nOrderbook Details:")
    print(f"Market params: {client.orderbook.market_params}")

    # Print market parameters
    market_params = client.orderbook.market_params
    print("\nMarket Parameters:")
    print(f"  Base Token: {market_params.base_asset}")
    print(f"  Quote Token: {market_params.quote_asset}")
    print(f"  Price Precision: {market_params.price_precision}")
    print(f"  Size Precision: {market_params.size_precision}")

        

    response = await client.get_user_orders()

    print("Raw API Response:")
    print(json.dumps(response))

    parsed_orders_list: list[ParsedOrder] = []

    if response and response.get('success'):
        raw_orders_data = response.get('data', {}).get('data', [])

        print(f"Found {len(raw_orders_data)} order entries in the response.")

        for order_data in raw_orders_data:
            try:
                # Pydantic handles parsing, validation, and aliasing using our local model
                parsed_order = ParsedOrder.model_validate(order_data)
                parsed_orders_list.append(parsed_order)
            except ValidationError as e:
                # Catch Pydantic's validation error
                print(f"Validation Error parsing order data: {order_data}. Error: {e}")
                # Continue parsing other orders
            except Exception as e: # Catch other potential errors
                print(f"Unexpected Error parsing order data: {order_data}. Error: {e}")

    else:
        print("Failed to fetch orders or API response indicated failure.")
        print(f"API Response: {response}")


    # Print the parsed orders
    print("Parsed Order Objects (using local model):")
    if parsed_orders_list:
        for order in parsed_orders_list:
            # Now you can access attributes directly from the ParsedOrder object
            print(f"  Order ID: {order.order_id}, "
                  f"Market: {order.market_address}, "
                  f"Side: {'Buy' if order.is_buy else 'Sell'}, "
                  f"Price: {order.price}, "
                  f"Size: {order.size}, "
                  f"Remaining: {order.remaining_size}, "
                  f"Time: {order.trigger_time}, "
                  f"Cancelled: {order.is_canceled}")
    else:
        print("  No orders were successfully parsed.")


    # Get order history
    
