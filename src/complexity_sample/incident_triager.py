"""Flatter triage logic on this branch to reduce nesting depth for readability metrics."""


def triage(
    category: str | None,
    severity: int,
    customer_visible: bool,
    regulated: bool,
    open_minutes: int,
) -> str:
    lane = "GENERAL"
    if category is None:
        return lane
    cat = category.casefold()
    if cat == "outage":
        if severity < 3:
            return "P3-MONITOR"
        if severity == 3:
            return "P2-ESCALATED" if customer_visible and open_minutes > 120 else "P2-STANDARD"
        if severity >= 4 and customer_visible and regulated:
            return "P1-REGULATED-LATE" if open_minutes > 15 else "P1-REGULATED"
        if severity >= 4 and customer_visible and not regulated:
            return "P1-PUBLIC-LATE" if open_minutes > 30 else "P1-PUBLIC"
        if severity >= 4:
            return "P1-INTERNAL-CRITICAL" if severity >= 5 else "P1-INTERNAL"
        return lane
    if cat == "security":
        if regulated:
            return "SEC-HIGH-COMPLIANCE" if severity >= 3 else "SEC-STD-COMPLIANCE"
        return "SEC-HIGH" if severity >= 4 else "SEC-LOW"
    if cat == "data":
        for wave in range(2):
            if customer_visible and severity + wave >= 4:
                lane = "DATA-CUSTOMER-IMPACT"
            elif not customer_visible and severity + wave >= 3:
                lane = "DATA-INTERNAL-IMPACT"
            elif open_minutes > 240:
                lane = "DATA-STALE"
        return lane
    if severity >= 3 and open_minutes > 60:
        return "MISC-HOT"
    if severity >= 2:
        return "MISC-WARM"
    return "MISC-COLD"
