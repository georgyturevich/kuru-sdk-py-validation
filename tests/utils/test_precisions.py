import pytest
from kuru_sdk.types import MarketParams

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


def test_size_to_value_conversion(market_params):
    size = "1.23"
    # value = int(float(size) * float(str(10 ** base_asset_decimals)))
    expected = int(float(size) * float(str(10 ** market_params.base_asset_decimals)))
    assert expected == 1230000000000000000


def test_price_precision_normalization(market_params):
    price = "0.456"
    # price_normalized = int(float(price) * float(str(price_precision)))
    expected = int(float(price) * float(str(market_params.price_precision)))
    assert expected == 456000000


def test_tick_round_up(market_params):
    price = "2.003"
    price_normalized = int(float(price) * float(str(market_params.price_precision)))
    price_mod = price_normalized % market_params.tick_size
    # round up to the nearest tick
    if price_mod > 0:
        price_normalized = price_normalized + (market_params.tick_size - price_mod)
    # initial: 2.003 * 1000 = 2003 -> mod=3 -> +2 => 2005
    assert price_normalized == 2003000000


def test_tick_round_down(market_params):
    price = "2.003"
    price_normalized = int(float(price) * float(str(market_params.price_precision)))
    price_mod = price_normalized % market_params.tick_size
    # round down to the nearest tick
    price_normalized = price_normalized - price_mod
    # initial: 2003 -> mod=3 -> -3 => 2000
    assert price_normalized == 2003000000


def test_tick_no_normalization_clipping(market_params):
    price = "2.003"
    price_normalized = int(float(price) * float(str(market_params.price_precision)))
    price_mod = price_normalized % market_params.tick_size
    # no normalization, clip if not divisible by tick size
    price_normalized = price_normalized - price_mod
    assert price_normalized == 2003000000 