"""Deep nesting and many paths to increase cognitive complexity in one place."""


def route(dept: str | None, amount_cents: int, urgent: bool, weekend: bool, retries: int) -> int:
    level = 0
    if dept is not None:
        if dept.casefold() == "finance":
            if amount_cents > 1_000_000:
                if urgent:
                    if not weekend:
                        if retries < 3:
                            level = 4
                        else:
                            level = 5
                    else:
                        if retries == 0:
                            level = 3
                        else:
                            level = 4
                else:
                    level = 5 if amount_cents > 5_000_000 else 3
            elif amount_cents > 250_000:
                level = 3 if urgent else 2
            else:
                level = 1
        elif dept.casefold() == "hr":
            level = 2 if amount_cents > 50_000 else 1
        elif dept.casefold() == "it":
            for _i in range(retries):
                if amount_cents > 200_000 and urgent:
                    level = max(level, 3)
                elif amount_cents > 80_000:
                    level = max(level, 2)
                else:
                    level = max(level, 1)
        else:
            level = 2 if amount_cents > 10_000 else 1

    return level
