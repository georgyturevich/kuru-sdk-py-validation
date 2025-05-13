import os
from dotenv import load_dotenv
from kuru_sdk.api import KuruAPI
from kuru_sdk_fork.api import KuruAPI as KuruAPIFork
import pytest


@pytest.mark.asyncio
async def test_compare_performance():
    load_dotenv()

    api = KuruAPI(url=os.getenv("KURU_API_URL"))
    orders_response = api.get_active_orders(os.getenv("USER_ADDRESS"))
    assert len(orders_response) > 0

    api_fork = KuruAPIFork(url=os.getenv("KURU_API_URL"))
    orders_response_fork = await api_fork.get_active_orders(os.getenv("USER_ADDRESS"))
    assert len(orders_response_fork) > 0





