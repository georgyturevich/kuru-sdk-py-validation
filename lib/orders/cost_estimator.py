from kuru_sdk.orderbook import Orderbook


async def estimate_required_quote_for_buy(
    orderbook: Orderbook,
    base_token_amount: float,
) -> float:
    """
    Estimates the amount of quote tokens required to buy a specified amount of base tokens,
    considering taker fees and the current state of the order book (asks).

    Args:
        orderbook: An initialized Orderbook instance.
        base_token_amount: The desired amount of base tokens to buy.

    Returns:
        The estimated amount of quote tokens needed.
    """

    """
        out += `takerFeeBps: ${takerFeeBps}\n`
        out += `grossBaseTokenAmount: ${grossBaseTokenAmount}\n`
        const l2OrderBook = await OrderBook.getL2OrderBook(
            providerOrSigner,
            orderbookAddress,
            marketParams,
            l2Book,
            contractVaultParams
        );

        let remainingBase = grossBaseTokenAmount;
        let requiredQuoteTokens = 0;

        out += `l2OrderBook.asks: ${l2OrderBook.asks.length}\n`
    """
    out = "\n"
    market_params = orderbook.market_params
    taker_fee = market_params.taker_fee_bps / 10000.0
    out += f"takerFeeBps: {taker_fee}\n"
    # Calculate the gross amount needed, accounting for taker fees
    gross_base_token_amount = base_token_amount / (1 - taker_fee)
    out += f"grossBaseTokenAmount: {gross_base_token_amount}\n"

    # Fetch the L2 order book (asks are sorted lowest price first)
    # get_l2_book returns [[price, size]] for asks and bids
    asks, _ = await orderbook.get_l2_book()
    out += f"l2OrderBook.asks: {len(asks)}\n"
    remaining_base = gross_base_token_amount
    required_quote_tokens = 0.0

    # Iterate through asks starting from the lowest price
    for price, order_size in asks:
        # price and order_size are already floats from get_l2_book

        if remaining_base <= 0:
            break

        # If the current order level can be fully consumed
        if remaining_base >= order_size:
            required_quote_tokens += order_size * price
            remaining_base -= order_size
        # If the current order level partially fills the remaining amount
        else:
            required_quote_tokens += remaining_base * price
            remaining_base = 0

    print(out)
    return required_quote_tokens
