import os

import pytest
import structlog
from dotenv import load_dotenv
from kuru_sdk import Orderbook
from web3 import Web3

from lib.constants import testnet_market_addresses
from lib.orders.cost_estimator import estimate_required_quote_for_buy

log = structlog.get_logger(__name__)

@pytest.mark.asyncio
async def test_estimate_required_quote_for_buy(settings):

    market_orderbook_addr = testnet_market_addresses["TEST_CHOG_MON"]
    orderbook = Orderbook(
        Web3(Web3.HTTPProvider(settings.full_rpc_url())), market_orderbook_addr, private_key=settings.private_key,
    )

    res = await estimate_required_quote_for_buy(orderbook, 1)

    assert res is not None

    log.info("Estimated required quote for buy", amount=f"{res:.22f}")
