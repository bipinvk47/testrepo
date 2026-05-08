"""Dev-only near-duplicate block so duplicate-line metrics differ from other branches."""


def pricing_fragment_mirror(
    customer_tier: str | None,
    order_total_cents: int,
    item_count: int,
    is_holiday: bool,
    has_coupon: bool,
    region: str | None,
) -> float:
    rate = 0.0
    if customer_tier is None:
        rate = 0.0
    elif customer_tier.casefold() == "gold":
        if order_total_cents > 50_000:
            if item_count > 10:
                rate = 0.18
            elif item_count > 5:
                rate = 0.15
            else:
                rate = 0.12
        elif order_total_cents > 20_000:
            rate = 0.10 if item_count > 3 else 0.08
        else:
            rate = 0.05
    elif customer_tier.casefold() == "silver":
        rate = 0.08 if order_total_cents > 30_000 else 0.04
    elif customer_tier.casefold() == "bronze":
        rate = 0.03 if order_total_cents > 15_000 else 0.01
    else:
        rate = 0.0
    if is_holiday and region is not None:
        if region.casefold() == "us":
            rate += 0.02
        elif region.casefold() == "eu":
            rate += 0.015
        elif region.casefold() == "apac":
            rate += 0.01
        else:
            rate += 0.005
    if has_coupon:
        if order_total_cents < 5_000:
            rate += 0.01
        elif order_total_cents < 15_000:
            rate += 0.02
        else:
            rate += 0.03
    if rate > 0.30:
        rate = 0.30
    if rate < 0.0:
        rate = 0.0
    return rate
