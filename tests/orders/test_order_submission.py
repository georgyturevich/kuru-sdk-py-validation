import os

from dotenv import load_dotenv
import pytest
from kuru_sdk.client_order_executor import ClientOrderExecutor
from kuru_sdk.types import OrderRequest
from web3 import Web3

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

    print("\n")
    print(f"Wallet address: {client.wallet_address}")

    balance = web3.eth.get_balance(client.wallet_address)
    print(f"Wallet balance: {web3.from_wei(balance, 'ether')} MON")

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
