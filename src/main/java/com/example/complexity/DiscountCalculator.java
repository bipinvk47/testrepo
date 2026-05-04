package com.example.complexity;

/**
 * Intentionally complex control flow for cyclomatic / cognitive complexity demos.
 */
public final class DiscountCalculator {

    private DiscountCalculator() {
    }

    public static double computeTieredDiscount(String customerTier, int orderTotalCents, int itemCount,
                                               boolean isHoliday, boolean hasCoupon, String region) {
        double rate = 0.0;
        if (customerTier == null) {
            rate = 0.0;
        } else if ("GOLD".equalsIgnoreCase(customerTier)) {
            if (orderTotalCents > 500_00) {
                if (itemCount > 10) {
                    rate = 0.18;
                } else if (itemCount > 5) {
                    rate = 0.15;
                } else {
                    rate = 0.12;
                }
            } else if (orderTotalCents > 200_00) {
                rate = itemCount > 3 ? 0.10 : 0.08;
            } else {
                rate = 0.05;
            }
        } else if ("SILVER".equalsIgnoreCase(customerTier)) {
            if (orderTotalCents > 300_00) {
                rate = 0.08;
            } else {
                rate = 0.04;
            }
        } else if ("BRONZE".equalsIgnoreCase(customerTier)) {
            rate = orderTotalCents > 150_00 ? 0.03 : 0.01;
        } else {
            switch (customerTier.toUpperCase()) {
                case "VIP":
                    rate = 0.20;
                    break;
                case "EMPLOYEE":
                    rate = 0.25;
                    break;
                case "PARTNER":
                    rate = 0.14;
                    break;
                default:
                    rate = 0.0;
                    break;
            }
        }

        if (isHoliday) {
            if ("US".equalsIgnoreCase(region)) {
                rate += 0.02;
            } else if ("EU".equalsIgnoreCase(region)) {
                rate += 0.015;
            } else if ("APAC".equalsIgnoreCase(region)) {
                rate += 0.01;
            } else {
                rate += 0.005;
            }
        }

        if (hasCoupon) {
            if (orderTotalCents < 50_00) {
                rate += 0.01;
            } else if (orderTotalCents < 150_00) {
                rate += 0.02;
            } else {
                rate += 0.03;
            }
        }

        if (rate > 0.30) {
            rate = 0.30;
        }
        if (rate < 0.0) {
            rate = 0.0;
        }
        return rate;
    }

    public static String summarizeLineItem(String sku, int qty, int unitPriceCents) {
        String prefix;
        if (sku == null || sku.isBlank()) {
            prefix = "UNKNOWN";
        } else if (sku.startsWith("DIG-")) {
            if (qty > 1) {
                if (unitPriceCents > 999) {
                    prefix = "DIG-BULK-HIGH";
                } else if (unitPriceCents > 199) {
                    prefix = "DIG-BULK-MID";
                } else {
                    prefix = "DIG-BULK-LOW";
                }
            } else {
                prefix = "DIG-SINGLE";
            }
        } else if (sku.startsWith("PHY-")) {
            prefix = qty > 5 ? "PHY-BULK" : "PHY-STD";
        } else {
            prefix = "GEN";
        }

        int lineTotal = qty * unitPriceCents;
        if (lineTotal < 0) {
            lineTotal = 0;
        }
        return prefix + ":" + lineTotal;
    }
}
