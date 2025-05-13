import math

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


# kuru_sdk.orderbook.Orderbook.prepare_market_buy normalizing
# kuru_sdk.orderbook.Orderbook.prepare_market_sell normalizing
def test_size_to_value_conversion(market_params: MarketParams):
    size = "1.23"

    expected = int(float(size) * float(str(10**market_params.base_asset_decimals)))
    assert expected == 1230000000000000000


# kuru_sdk.orderbook.Orderbook.normalize_with_precision
def test_price_precision_normalization(market_params: MarketParams):
    price = "0.456"

    expected = int(float(price) * float(str(market_params.price_precision)))
    assert expected == 456000000


# kuru_sdk.orderbook.Orderbook.prepare_buy_order round_up
def test_tick_round_up(market_params: MarketParams):
    test_cases = [
        ("2.003000007", 2003000010),
        ("1.5", 1500000010),
        ("0.00000123", 1240),
        ("3.1", 3100000010),
        ("3.14159265", 3141592660),
        ("0.00000202", 2030),
        ("0.00000282", 2830),
        ("0.00000281", 2820),
        ("0.00000101", 1020),
        ("0.00000200", 2010),
        ("0.00000201", 2010),
        ("0.00000219", 2200),
        ("0.00000229", 2290),
        ("0.00000239", 2390),
        ("0.00000249", 2490),
        ("0.00000259", 2590),
        ("0.00000269", 2690),
        ("0.00000279", 2790),

        ("0.00000301", 3010),
        ("0.00000401", 4010),
        ("0.00000501", 5010),
        ("0.00000601", 6010),
        ("0.00000701", 7010),
        ("0.00000801", 8010),
        ("0.00000901", 9010),
        ("0.00001001", 10010),
        ("10.00000007", 10000000070),
    ]
    
    for price, expected in test_cases:
        # round up to the nearest tick
        price_normalized = normalize_with_precision_and_tick(price, "round_up", market_params=market_params)
        
        assert price_normalized == expected, f"Failed for price {price}, got {price_normalized}, expected {expected}"


# kuru_sdk.orderbook.Orderbook.prepare_buy_order round_down|default
def test_tick_round_down(market_params: MarketParams):
    test_cases = [
        ("2.003000007", 2003000000),
        ("1.5", 1500000000),
        ("0.00000123", 1230),
        ("3.14159265", 3141592650),
        ("0.00000202", 2020),
        ("0.00000282", 2820),
        ("0.00000281", 2810),
        ("0.00000211", 2110),
        ("0.00000101", 1010),
        ("0.00000201", 2000),
        ("0.00000301", 3010),
        ("0.00000401", 4000),
        ("0.00000501", 5010),
        ("0.00000601", 6010),
        ("0.00000701", 7010),
        ("0.00000801", 8000),
        ("0.00000901", 9010),
        ("0.00000900", 9000),
        ("0.00001001", 10010),
        
        #("10.00000007", 10000000070),
    ]
    
    for price, expected in test_cases:
        # round down to the nearest tick
        price_normalized = normalize_with_precision_and_tick(price, "round_down", market_params=market_params)

        assert price_normalized == expected, f"Failed for price {price}, got {price_normalized}, expected {expected}"


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

def test_math_floor():
    assert math.floor(1.2) == 1
    assert math.floor(1.0) == 1


def normalize_with_precision_and_tick(
        price: str,
        tick_normalization: str,
        market_params
) -> int:
    """Normalize price and size with contract precision"""

    price_normalized = float(price) * float(str(market_params.price_precision))

    if tick_normalization == "round_up":
        price_normalized = price_normalized + (market_params.tick_size - price_normalized % market_params.tick_size)
    elif tick_normalization == "round_down":
        price_normalized = price_normalized - (price_normalized % market_params.tick_size)
    else:
        price_normalized = price_normalized - (price_normalized % market_params.tick_size)

    return int(price_normalized)

