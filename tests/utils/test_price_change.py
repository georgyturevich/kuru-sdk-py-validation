from lib.utils.price_change import price_suffix_change

def test_price_change_basic():
    # Test basic case with small change
    assert price_suffix_change('0.000200', 1) == '0.000201'
    assert price_suffix_change('0.000200', 11) == '0.000211'
    assert price_suffix_change('0.000200', 211) == '0.000211'
    assert price_suffix_change('0.002000', 211) == '0.002211'

def test_price_change_with_larger_numbers():
    # Test with larger numbers
    assert price_suffix_change('1.000200', 1) == '1.000201'
    assert price_suffix_change('10.000200', 11) == '10.000211'
    assert price_suffix_change('100.000200', 211) == '100.000211'

def test_price_change_with_different_decimal_places():
    # Test with different decimal place lengths
    assert price_suffix_change('0.200000', 1) == '0.200001'
    assert price_suffix_change('0.200000', 11) == '0.200011'
    assert price_suffix_change('0.200000', 211) == '0.200211'

def test_price_change_edge_cases():
    # Test edge cases
    assert price_suffix_change('0.000000', 1) == '0.000001'
    assert price_suffix_change('0.000000', 999) == '0.000999'
    assert price_suffix_change('999.000000', 1) == '999.000001'

def test_price_change_invalid_input():
    
    v = price_suffix_change('0.000200', -1)
    assert v == '0.0002-1'
    print(v)