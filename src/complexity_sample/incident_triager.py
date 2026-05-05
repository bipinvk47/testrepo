"""Deeply nested decision tree aimed at cognitive-complexity metrics."""


def triage(
    category: str | None,
    severity: int,
    customer_visible: bool,
    regulated: bool,
    open_minutes: int,
) -> str:
    lane = "GENERAL"
    if category is not None:
        if category.casefold() == "outage":
            if severity >= 4:
                if customer_visible:
                    if regulated:
                        if open_minutes > 15:
                            lane = "P1-REGULATED-LATE"
                        else:
                            lane = "P1-REGULATED"
                    else:
                        if open_minutes > 30:
                            lane = "P1-PUBLIC-LATE"
                        else:
                            lane = "P1-PUBLIC"
                else:
                    lane = "P1-INTERNAL-CRITICAL" if severity >= 5 else "P1-INTERNAL"
            elif severity == 3:
                if customer_visible and open_minutes > 120:
                    lane = "P2-ESCALATED"
                else:
                    lane = "P2-STANDARD"
            else:
                lane = "P3-MONITOR"
        elif category.casefold() == "security":
            if regulated:
                if severity >= 3:
                    lane = "SEC-HIGH-COMPLIANCE"
                else:
                    lane = "SEC-STD-COMPLIANCE"
            elif severity >= 4:
                lane = "SEC-HIGH"
            else:
                lane = "SEC-LOW"
        elif category.casefold() == "data":
            for wave in range(2):
                if customer_visible and severity + wave >= 4:
                    lane = "DATA-CUSTOMER-IMPACT"
                elif not customer_visible and severity + wave >= 3:
                    lane = "DATA-INTERNAL-IMPACT"
                elif open_minutes > 240:
                    lane = "DATA-STALE"
        else:
            if severity >= 3 and open_minutes > 60:
                lane = "MISC-HOT"
            elif severity >= 2:
                lane = "MISC-WARM"
            else:
                lane = "MISC-COLD"

    return lane
