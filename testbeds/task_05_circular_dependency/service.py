def get_checkout_price(price: float, is_vip: bool) -> float:
    """Calculates checkout price for a customer."""
    if not is_vip:
        return price
    # BUG: references undefined calculate_discount_v2
    discount = calculate_discount_v2(price)
    return price - discount
