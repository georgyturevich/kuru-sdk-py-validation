import pytest
from kuru_sdk.types import MarketParams
import math

@pytest.fixture
def market_params():
    
    return MarketParams(
        price_precision=1000000000,
        size_precision=1000000000,
        base_asset="0x7E9953A11E606187be268C3A6Ba5f36635149C81",
        base_asset_decimals=18,
        quote_asset="0x0000000000000000000000000000000000000000",
        quote_asset_decimals=18,
        tick_size=10,
        min_size=1000000000000,
        max_size=1000000000000000000,
        taker_fee_bps=30,
        maker_fee_bps=10,
    )

# kuru_sdk.orderbook.Orderbook.prepare_market_buy normalizing
# kuru_sdk.orderbook.Orderbook.prepare_market_sell normalizing
def test_size_to_value_conversion(market_params: MarketParams):
    size = "1.23"

    expected = int(float(size) * float(str(10 ** market_params.base_asset_decimals)))
    assert expected == 1230000000000000000


# kuru_sdk.orderbook.Orderbook.normalize_with_precision
def test_price_precision_normalization(market_params: MarketParams):
    price = "0.456"

    expected = int(float(price) * float(str(market_params.price_precision)))
    assert expected == 456000000

# kuru_sdk.orderbook.Orderbook.prepare_buy_order round_up
def test_tick_round_up(market_params: MarketParams):
    price = "2.003000007"
    price_normalized = int(float(price) * float(str(market_params.price_precision)))
    price_mod = price_normalized % market_params.tick_size
    # round up to the nearest tick
    if price_mod > 0:
        price_normalized = price_normalized + (market_params.tick_size - price_mod)
    # initial: 2.003 * 1000 = 2003 -> mod=3 -> +2 => 2005
    assert price_normalized == 2003000010


# kuru_sdk.orderbook.Orderbook.prepare_buy_order round_down|default
def test_tick_round_down(market_params: MarketParams):
    price = "2.003000007"

    price_normalized = int(float(price) * float(str(market_params.price_precision)))
    price_mod = price_normalized % market_params.tick_size
    # round down to the nearest tick
    price_normalized = price_normalized - price_mod
    # initial: 2003 -> mod=3 -> -3 => 2000
    assert price_normalized == 2003000000


# kuru_sdk.orderbook.Orderbook.prepare_buy_order
def test_tick_normalization_round_up_with_ceil(market_params: MarketParams):
    # Use ceil to round up to the nearest tick
    normalized_price = 2002999998
    result = market_params.tick_size * math.ceil(float(normalized_price) / market_params.tick_size)
    assert result == 2003000000

# kuru_sdk.orderbook.Orderbook.prepare_buy_order
def test_tick_normalization_round_down_with_floor(market_params: MarketParams):
    # Use floor to round down to the nearest tick
    normalized_price = 2003000003
    result = market_params.tick_size * math.floor(float(normalized_price) / market_params.tick_size)
    assert result == 2003000000 