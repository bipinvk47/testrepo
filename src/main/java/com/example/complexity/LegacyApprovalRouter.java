package com.example.complexity;

/**
 * Deep nesting and many paths to increase cognitive complexity in one place.
 */
public final class LegacyApprovalRouter {

    private LegacyApprovalRouter() {
    }

    public static int route(String dept, int amountCents, boolean urgent, boolean weekend, int retries) {
        int level = 0;
        if (dept != null) {
            if ("FINANCE".equalsIgnoreCase(dept)) {
                if (amountCents > 1_000_000) {
                    if (urgent) {
                        if (!weekend) {
                            if (retries < 3) {
                                level = 4;
                            } else {
                                level = 5;
                            }
                        } else {
                            if (retries == 0) {
                                level = 3;
                            } else {
                                level = 4;
                            }
                        }
                    } else {
                        if (amountCents > 5_000_000) {
                            level = 5;
                        } else {
                            level = 3;
                        }
                    }
                } else if (amountCents > 250_000) {
                    level = urgent ? 3 : 2;
                } else {
                    level = 1;
                }
            } else if ("HR".equalsIgnoreCase(dept)) {
                if (amountCents > 50_000) {
                    level = 2;
                } else {
                    level = 1;
                }
            } else if ("IT".equalsIgnoreCase(dept)) {
                for (int i = 0; i < retries; i++) {
                    if (amountCents > 200_000 && urgent) {
                        level = Math.max(level, 3);
                    } else if (amountCents > 80_000) {
                        level = Math.max(level, 2);
                    } else {
                        level = Math.max(level, 1);
                    }
                }
            } else {
                level = amountCents > 10_000 ? 2 : 1;
            }
        }
        return level;
    }
}
