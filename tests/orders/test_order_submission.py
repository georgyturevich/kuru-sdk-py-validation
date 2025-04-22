import asyncio
import os

from dotenv import load_dotenv
import pytest
from eth_utils import to_wei
from kuru_sdk import Orderbook
from kuru_sdk.api import KuruAPI
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest, TxOptions
from web3 import Web3

from lib.constants import testnet_market_addresses
from lib.orders.cost_estimator import estimate_required_quote_for_buy
from lib.utils.format import format_orders_list_payload


@pytest.mark.asyncio
async def test_limit_order_submission():

    load_dotenv()

    pair = "DAK_MON"
    market_orderbook_addr = testnet_market_addresses[pair]
    web3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
    orderbook = Orderbook(
        web3, market_orderbook_addr, private_key=os.getenv("PK"),
    )



    est_price = await estimate_required_quote_for_buy(orderbook, 1)
    low_price = est_price / 100

    # round the following variable like in js Math.floor
    size = 0.2 / low_price
    size = int(size)


    print(f"\nBuying {pair} at {low_price} for {size} units")

    client = ClientOrderExecutor(
        web3=web3,
        contract_address=market_orderbook_addr,
        private_key=os.getenv("PK"),
    )

    print(f"Wallet address: {client.wallet_address}")

    api = KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"))
    orders = format_orders_list_payload(orders_response)
    assert len(orders) > 0

    print(f"\nMarket orderbook address: {market_orderbook_addr}")
    print(f"\nOrders length: {len(orders)}")

    # Create an order
    
    order = OrderRequest(
        market_address=market_orderbook_addr,
        order_type='limit',
        side='buy',
        #price="0.0000003",
        #price="0.000076140",
        #price=0.000015,
        #price=0.0000003,
        price=low_price,
        size=size,
        #size="1000",
        cloid="test_order_1"
    )

    print(f"Wallet address: {orderbook.wallet_address}")
    # Submit order
    tx_hash = await client.place_order(order)

    # Verify tx_hash exists
    assert tx_hash is not None
    assert len(tx_hash) > 0

    print(tx_hash)

    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"))
    orders = format_orders_list_payload(orders_response)


    print(f"\nOrders length 2: {len(orders)}")

@pytest.mark.asyncio
async def test_example_place_order():
    load_dotenv()

    web3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
    market_address = "0x05e6f736b5dedd60693fa806ce353156a1b73cf3" #// CHOG-MON https://www.kuru.io/trade/0x05e6f736b5dedd60693fa806ce353156a1b73cf3
    client = ClientOrderExecutor(
        web3=web3,
        contract_address=market_address,
        private_key=os.getenv("PRIVATE_KEY"),
    )

    print(f"Wallet address: {client.wallet_address}")

    balance = web3.eth.get_balance(client.wallet_address)
    print(f"Current balance: {web3.from_wei(balance, 'ether')} MON")

    order = OrderRequest(
        market_address=market_address,
        order_type='limit',
        side='buy',
        price="0.00000284",
        size="10000",
        post_only=False,
        cloid="mm_1"
    )
    print(f"Placing limit buy order: {order.size} units at {order.price}")
    tx_hash = await client.place_order(order)

    assert tx_hash is not None
    assert len(tx_hash) > 0
