"""Many independent branches and loops to raise cyclomatic complexity without extreme nesting."""

from decimal import Decimal


def compute_eligibility_score(
    age: int,
    region: str | None,
    employed: bool,
    dependents: int,
    prior_claims: int,
    plan_code: str | None,
    income: Decimal,
    flagged: bool,
    late_payments: int,
    co_applicant: bool,
) -> int:
    score = 0

    if age < 18:
        score -= 50
    elif age < 25:
        score += 2
    elif age < 40:
        score += 5
    elif age < 60:
        score += 8
    else:
        score += 4

    if region is None:
        score -= 5
    elif region.casefold() == "na":
        score += 3
    elif region.casefold() == "eu":
        score += 2
    elif region.casefold() == "apac":
        score += 1
    else:
        score += 0

    score += 6 if employed else -4
    score += max(0, min(5, dependents))

    if prior_claims == 0:
        score += 4
    elif prior_claims == 1:
        score += 1
    elif prior_claims == 2:
        score -= 2
    else:
        score -= 8

    if plan_code is None:
        score -= 3
    else:
        match plan_code.upper():
            case "A1":
                score += 5
            case "B2":
                score += 4
            case "C3":
                score += 2
            case "D4":
                score += 0
            case "E5":
                score -= 2
            case _:
                score -= 1

    if income < Decimal("20000"):
        score -= 6
    elif income < Decimal("45000"):
        score += 1
    elif income < Decimal("90000"):
        score += 5
    else:
        score += 7

    if flagged:
        score -= 10

    for i in range(late_payments):
        if i == 0:
            score -= 1
        elif i < 3:
            score -= 2
        else:
            score -= 4

    if co_applicant:
        if score < 0:
            score += 2
        elif score < 10:
            score += 4
        else:
            score += 3

    return score
