package com.example.complexity;

public final class CopyPastePricingFragment {

    private CopyPastePricingFragment() {
    }

    public static double pricingFragmentMirror(
            String customerTier,
            int orderTotalCents,
            int itemCount,
            boolean isHoliday,
            boolean hasCoupon,
            String region) {
        double rate = 0.0;
        if (customerTier == null) {
            rate = 0.0;
        } else if (customerTier.equalsIgnoreCase("gold")) {
            if (orderTotalCents > 50000) {
                if (itemCount > 10) {
                    rate = 0.18;
                } else if (itemCount > 5) {
                    rate = 0.15;
                } else {
                    rate = 0.12;
                }
            } else if (orderTotalCents > 20000) {
                rate = itemCount > 3 ? 0.10 : 0.08;
            } else {
                rate = 0.05;
            }
        } else if (customerTier.equalsIgnoreCase("silver")) {
            rate = orderTotalCents > 30000 ? 0.08 : 0.04;
        } else if (customerTier.equalsIgnoreCase("bronze")) {
            rate = orderTotalCents > 15000 ? 0.03 : 0.01;
        } else {
            rate = 0.0;
        }
        if (isHoliday && region != null) {
            if (region.equalsIgnoreCase("us")) {
                rate += 0.02;
            } else if (region.equalsIgnoreCase("eu")) {
                rate += 0.015;
            } else if (region.equalsIgnoreCase("apac")) {
                rate += 0.01;
            } else {
                rate += 0.005;
            }
        }
        if (hasCoupon) {
            if (orderTotalCents < 5000) {
                rate += 0.01;
            } else if (orderTotalCents < 15000) {
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
}
