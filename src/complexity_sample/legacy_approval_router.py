"""Flatter approval routing on this branch for improved readability-style metrics."""


def route(dept: str | None, amount_cents: int, urgent: bool, weekend: bool, retries: int) -> int:
    if dept is None:
        return 0
    d = dept.casefold()
    if d == "finance":
        if amount_cents <= 250_000:
            return 1
        if amount_cents <= 1_000_000:
            return 3 if urgent else 2
        if urgent and not weekend and retries < 3:
            return 4
        if urgent and not weekend:
            return 5
        if weekend:
            return 3 if retries == 0 else 4
        return 5 if amount_cents > 5_000_000 else 3
    if d == "hr":
        return 2 if amount_cents > 50_000 else 1
    if d == "it":
        level = 0
        for _i in range(retries):
            if amount_cents > 200_000 and urgent:
                level = max(level, 3)
            elif amount_cents > 80_000:
                level = max(level, 2)
            else:
                level = max(level, 1)
        return level
    return 2 if amount_cents > 10_000 else 1
