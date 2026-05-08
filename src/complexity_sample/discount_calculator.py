"""Simplified control flow on this branch to lift readability-oriented white-box scores."""


def compute_tiered_discount(
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
        spend_boost = min(0.10, max(0.0, (order_total_cents - 20_000) / 500_000))
        qty_boost = min(0.08, max(0.0, (item_count - 3) * 0.01))
        rate = min(0.18, 0.05 + spend_boost + qty_boost)
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
        key = (region or "").casefold()
        rate += {"us": 0.02, "eu": 0.015, "apac": 0.01}.get(key, 0.005)

    if has_coupon:
        rate += 0.01 if order_total_cents < 5_000 else 0.02 if order_total_cents < 15_000 else 0.03

    return max(0.0, min(0.30, rate))


def summarize_line_item(sku: str | None, qty: int, unit_price_cents: int) -> str:
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
