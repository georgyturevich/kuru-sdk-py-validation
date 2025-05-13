import os
from datetime import datetime, timedelta

import kuru_sdk.api as KuruAPI
import kuru_sdk_fork
import pytest
from dotenv import load_dotenv

from lib.constants import testnet_market_addresses


@pytest.mark.asyncio
async def test_get_user_orders():
    load_dotenv()
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"))
    assert len(orders_response) > 0

    print(f"\nUser order: {orders_response}")


@pytest.mark.asyncio
async def test_get_orders_by_ids():
    load_dotenv()
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))

    user_orders = api.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    assert len(user_orders) > 0

    order_ids = [order.order_id for order in user_orders]
    orders = api.get_orders_by_ids(testnet_market_addresses["TEST_CHOG_MON"], order_ids)

    assert len(orders) > 0
    print(f"\nOrders by IDs: {orders}")


@pytest.mark.asyncio
async def test_get_active_orders():
    load_dotenv()

    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_active_orders(os.getenv("USER_ADDRESS"))
    assert len(orders_response) > 0

    print(f"\nActive orders: {orders_response}")


@pytest.mark.asyncio
async def test_get_orders_by_sdk_cloid():
    load_dotenv()
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))

    user_orders = api.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    assert len(user_orders) > 0

    cloids = []
    for order in user_orders:
        order_type = "buy" if order.is_buy == True else "sell"
        tx_hash = '0x' + order.transaction_hash \
                if not order.transaction_hash.startswith('0x') else order.transaction_hash
        cloid = f"{tx_hash}_{order_type}_{order.price}"
        cloids.append(cloid)
    orders = api.get_orders_by_sdk_cloid(
        testnet_market_addresses["TEST_CHOG_MON"], 
        os.getenv("USER_ADDRESS"),
        cloids,
    )

    assert len(orders) > 0
    print(f"\nOrders by client order IDs: {orders}")


@pytest.mark.asyncio
async def test_get_trades():
    load_dotenv()
    print(f"User address: {os.getenv('USER_ADDRESS')}")
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))

    trades = api.get_trades(testnet_market_addresses["TEST_CHOG_MON"], os.getenv("USER_ADDRESS"))

    assert len(trades) > 0
    print(trades)
