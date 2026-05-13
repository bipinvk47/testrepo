package com.example.complexity;

public final class IncidentTriager {

    private IncidentTriager() {
    }

    public static String triage(
            String category,
            int severity,
            boolean customerVisible,
            boolean regulated,
            int openMinutes) {
        String lane = "GENERAL";
        if (category != null) {
            if (category.equalsIgnoreCase("outage")) {
                if (severity >= 4) {
                    if (customerVisible) {
                        if (regulated) {
                            if (openMinutes > 15) {
                                lane = "P1-REGULATED-LATE";
                            } else {
                                lane = "P1-REGULATED";
                            }
                        } else {
                            if (openMinutes > 30) {
                                lane = "P1-PUBLIC-LATE";
                            } else {
                                lane = "P1-PUBLIC";
                            }
                        }
                    } else {
                        lane = severity >= 5 ? "P1-INTERNAL-CRITICAL" : "P1-INTERNAL";
                    }
                } else if (severity == 3) {
                    if (customerVisible && openMinutes > 120) {
                        lane = "P2-ESCALATED";
                    } else {
                        lane = "P2-STANDARD";
                    }
                } else {
                    lane = "P3-MONITOR";
                }
            } else if (category.equalsIgnoreCase("security")) {
                if (regulated) {
                    if (severity >= 3) {
                        lane = "SEC-HIGH-COMPLIANCE";
                    } else {
                        lane = "SEC-STD-COMPLIANCE";
                    }
                } else if (severity >= 4) {
                    lane = "SEC-HIGH";
                } else {
                    lane = "SEC-LOW";
                }
            } else if (category.equalsIgnoreCase("data")) {
                for (int wave = 0; wave < 2; wave++) {
                    if (customerVisible && severity + wave >= 4) {
                        lane = "DATA-CUSTOMER-IMPACT";
                    } else if (!customerVisible && severity + wave >= 3) {
                        lane = "DATA-INTERNAL-IMPACT";
                    } else if (openMinutes > 240) {
                        lane = "DATA-STALE";
                    }
                }
            } else {
                if (severity >= 3 && openMinutes > 60) {
                    lane = "MISC-HOT";
                } else if (severity >= 2) {
                    lane = "MISC-WARM";
                } else {
                    lane = "MISC-COLD";
                }
            }
        }
        return lane;
    }
}
