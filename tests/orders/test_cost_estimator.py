import os

import pytest
from dotenv import load_dotenv
from kuru_sdk import Orderbook
from web3 import Web3

from lib.constants import testnet_market_addresses
from lib.orders.cost_estimator import estimate_required_quote_for_buy


@pytest.mark.asyncio
async def test_estimate_required_quote_for_buy():

    load_dotenv()

    market_orderbook_addr = testnet_market_addresses["TEST_CHOG_MON"]
    orderbook = Orderbook(
        Web3(Web3.HTTPProvider(os.getenv("RPC_URL"))), market_orderbook_addr, private_key=os.getenv("PK"),
    )

    res = await estimate_required_quote_for_buy(orderbook, 1)

    assert res is not None

    print(f"Estimated required quote for buy: {res:.22f}")
