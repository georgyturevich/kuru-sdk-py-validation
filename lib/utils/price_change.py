def price_suffix_change(price: str, suffix: int) -> str:
    """Replace the last N digits of a price string with a new suffix.

    Args:
        price (str): Price string (e.g., '0.000200')
        suffix (int): New suffix to append

    Returns:
        str: Modified price string

    Examples:
        >>> price_suffix_change('0.000200', 1)
        '0.000201'
        >>> price_suffix_change('0.000200', 211)
        '0.000211'
    """
    str_suffix = str(suffix)
    price = price[:-len(str_suffix)]    
    price += str_suffix
    return price
