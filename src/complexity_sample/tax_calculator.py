"""Near-duplicate of discount_calculator logic to surface code duplication in analysis tools."""


def compute_tiered_surcharge(
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
        match customer_tier.upper():
            case "VIP":
                rate = 0.20
            case "EMPLOYEE":
                rate = 0.25
            case "PARTNER":
                rate = 0.14
            case _:
                rate = 0.0

    if is_holiday:
        if region is not None and region.casefold() == "us":
            rate += 0.02
        elif region is not None and region.casefold() == "eu":
            rate += 0.015
        elif region is not None and region.casefold() == "apac":
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


def summarize_physical_line(sku: str | None, qty: int, unit_price_cents: int) -> str:
    if sku is None or not sku.strip():
        prefix = "UNKNOWN"
    elif sku.startswith("DIG-"):
        if qty > 1:
            if unit_price_cents > 999:
                prefix = "DIG-BULK-HIGH"
            elif unit_price_cents > 199:
                prefix = "DIG-BULK-MID"
            else:
                prefix = "DIG-BULK-LOW"
        else:
            prefix = "DIG-SINGLE"
    elif sku.startswith("PHY-"):
        prefix = "PHY-BULK" if qty > 5 else "PHY-STD"
    else:
        prefix = "GEN"

    line_total = qty * unit_price_cents
    if line_total < 0:
        line_total = 0

    return prefix + ":" + str(line_total)
