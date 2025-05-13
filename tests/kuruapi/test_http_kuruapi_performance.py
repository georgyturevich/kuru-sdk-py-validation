import os
from dotenv import load_dotenv
from kuru_sdk.api import KuruAPI
from kuru_sdk_fork.api import KuruAPI as KuruAPIFork
import pytest


@pytest.mark.asyncio
async def test_compare_performance():
    load_dotenv()

    api = KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    assert len(orders_response) > 0
    print(f"\nUser orders: {orders_response}")

    api_fork = KuruAPIFork(url=os.getenv("KURU_API_URL"))
    orders_response_fork = await api_fork.get_user_orders(os.getenv("USER_ADDRESS"), limit=3)
    assert len(orders_response_fork) > 0
    print(f"\nUser orders from fork: {orders_response_fork}")





