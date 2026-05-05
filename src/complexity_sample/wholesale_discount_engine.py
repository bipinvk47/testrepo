"""Near-duplicate of retail_discount_engine (different literals, same structure) for duplication analysis."""

from decimal import Decimal


def compute_wholesale_rate(
    tier: str | None, subtotal: Decimal, units: int, weekend_promo: bool
) -> Decimal:
    if tier is None:
        return Decimal("0")

    r = Decimal("0")
    if tier.casefold() == "plus":
        if subtotal > Decimal("750"):
            if units > 10:
                r = Decimal("0.14")
            elif units > 5:
                r = Decimal("0.11")
            else:
                r = Decimal("0.09")
        elif subtotal > Decimal("300"):
            r = Decimal("0.07") if units > 3 else Decimal("0.05")
        else:
            r = Decimal("0.03")
    elif tier.casefold() == "standard":
        r = Decimal("0.05") if subtotal > Decimal("200") else Decimal("0.02")
    elif tier.casefold() == "basic":
        r = Decimal("0.02") if subtotal > Decimal("100") else Decimal("0.01")
    else:
        match tier.upper():
            case "VIP_WHOLESALE":
                r = Decimal("0.16")
            case "STAFF":
                r = Decimal("0.22")
            case "AFFILIATE":
                r = Decimal("0.12")
            case _:
                r = Decimal("0")

    if weekend_promo:
        if subtotal < Decimal("50"):
            r += Decimal("0.01")
        elif subtotal < Decimal("130"):
            r += Decimal("0.02")
        else:
            r += Decimal("0.03")

    if r > Decimal("0.28"):
        return Decimal("0.28")
    if r < Decimal("0"):
        return Decimal("0")
    return r


def classify_sku_bucket(code: str | None, qty: int, unit_price: Decimal) -> str:
    if code is None or not code.strip():
        bucket = "UNLABELED"
    elif code.startswith("W-"):
        if qty > 2:
            if unit_price > Decimal("44.99"):
                bucket = "W-BULK-PREMIUM"
            elif unit_price > Decimal("17.99"):
                bucket = "W-BULK-MID"
            else:
                bucket = "W-BULK-VALUE"
        else:
            bucket = "W-SINGLE"
    elif code.startswith("C-"):
        bucket = "C-BULK" if qty > 8 else "C-STD"
    else:
        bucket = "OTHER"

    ext = qty * unit_price
    if ext < Decimal("0"):
        ext = Decimal("0")

    return bucket + "|" + f"{ext:.2f}"
