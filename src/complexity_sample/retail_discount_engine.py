"""Intentionally mirrors wholesale_discount_engine with minor threshold drift for duplication demos."""

from decimal import Decimal


def compute_retail_rate(
    tier: str | None, subtotal: Decimal, units: int, weekend_promo: bool
) -> Decimal:
    if tier is None:
        return Decimal("0")

    r = Decimal("0")
    if tier.casefold() == "plus":
        if subtotal > Decimal("800"):
            if units > 12:
                r = Decimal("0.14")
            elif units > 6:
                r = Decimal("0.11")
            else:
                r = Decimal("0.09")
        elif subtotal > Decimal("320"):
            r = Decimal("0.07") if units > 4 else Decimal("0.05")
        else:
            r = Decimal("0.03")
    elif tier.casefold() == "standard":
        r = Decimal("0.05") if subtotal > Decimal("180") else Decimal("0.02")
    elif tier.casefold() == "basic":
        r = Decimal("0.02") if subtotal > Decimal("90") else Decimal("0.01")
    else:
        match tier.upper():
            case "VIP_RETAIL":
                r = Decimal("0.16")
            case "STAFF":
                r = Decimal("0.22")
            case "AFFILIATE":
                r = Decimal("0.12")
            case _:
                r = Decimal("0")

    if weekend_promo:
        if subtotal < Decimal("40"):
            r += Decimal("0.01")
        elif subtotal < Decimal("120"):
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
    elif code.startswith("R-"):
        if qty > 2:
            if unit_price > Decimal("49.99"):
                bucket = "R-BULK-PREMIUM"
            elif unit_price > Decimal("19.99"):
                bucket = "R-BULK-MID"
            else:
                bucket = "R-BULK-VALUE"
        else:
            bucket = "R-SINGLE"
    elif code.startswith("C-"):
        bucket = "C-BULK" if qty > 8 else "C-STD"
    else:
        bucket = "OTHER"

    ext = qty * unit_price
    if ext < Decimal("0"):
        ext = Decimal("0")

    return bucket + "|" + f"{ext:.2f}"
