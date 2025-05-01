import os
import time
from datetime import datetime, timedelta

import kuru_sdk.api as KuruAPI
import pytest
from dotenv import load_dotenv

from lib.constants import testnet_market_addresses
from lib.utils.format import format_orders_list_payload


@pytest.mark.asyncio
def test_get_user_orders():
    load_dotenv()
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"))
    orders = format_orders_list_payload(orders_response)
    assert len(orders) > 0

    print(f"\nOrders: {orders}")


# @pytest.mark.asyncio
# def test_get_orders_by_ids():
#     api = KuruAPI.KuruAPI("http://localhost:3000/api/v2")
#     orders = api.get_orders_by_ids("0x8de88cf2bc9b8591fa547dd38775bc83361f8b4e", [7,2,3])
#     print(orders)


@pytest.mark.asyncio
def test_get_active_orders():
    load_dotenv()

    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_active_orders(os.getenv("USER_ADDRESS"))
    assert orders_response["data"] is not None
    assert orders_response["data"]["data"] is not None
    assert len(orders_response["data"]["data"]) > 0

    # TODO: Consider what to todo with discrepancies between get_user_orders and get_active_orders
    # orders = format_orders_list_payload(orders_response)
    # assert len(orders) > 0

    # print(f"\nOrders: {orders}")


# @pytest.mark.asyncio
# def test_get_order_history():
#     api = KuruAPI.KuruAPI("http://api.kuru.io/api/v2")
#     orders = api.get_order_history("0xf7f70cb1a1b1128272d1c2751ab788b1226303b1")
#     print(orders)


@pytest.mark.asyncio
def test_get_trades():
    load_dotenv()
    print(f"User address: {os.getenv("USER_ADDRESS")}")
    api = KuruAPI.KuruAPI(url=os.getenv("KURU_API_URL"))

    start_timestamp = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    # trades = api.get_trades(testnet_market_addresses["TEST_CHOG_MON"], os.getenv("USER_ADDRESS"), start_timestamp=start_timestamp)
    trades = api.get_trades(testnet_market_addresses["TEST_CHOG_MON"], os.getenv("USER_ADDRESS"))

    assert len(trades) > 0
    print(trades)
