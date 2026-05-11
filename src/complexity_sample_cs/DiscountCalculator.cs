using System;

namespace ComplexitySample
{
    public static class DiscountCalculator
    {
        public static double ComputeTieredDiscount(
            string? customerTier,
            int orderTotalCents,
            int itemCount,
            bool isHoliday,
            bool hasCoupon,
            string? region)
        {
            double rate = 0.0;
            if (customerTier == null)
            {
                rate = 0.0;
            }
            else if (customerTier.Equals("gold", StringComparison.OrdinalIgnoreCase))
            {
                if (orderTotalCents > 50000)
                {
                    if (itemCount > 10)
                    {
                        rate = 0.18;
                    }
                    else if (itemCount > 5)
                    {
                        rate = 0.15;
                    }
                    else
                    {
                        rate = 0.12;
                    }
                }
                else if (orderTotalCents > 20000)
                {
                    rate = itemCount > 3 ? 0.10 : 0.08;
                }
                else
                {
                    rate = 0.05;
                }
            }
            else if (customerTier.Equals("silver", StringComparison.OrdinalIgnoreCase))
            {
                rate = orderTotalCents > 30000 ? 0.08 : 0.04;
            }
            else if (customerTier.Equals("bronze", StringComparison.OrdinalIgnoreCase))
            {
                rate = orderTotalCents > 15000 ? 0.03 : 0.01;
            }
            else
            {
                switch (customerTier.ToUpperInvariant())
                {
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

            if (isHoliday)
            {
                if (region != null && region.Equals("us", StringComparison.OrdinalIgnoreCase))
                {
                    rate += 0.02;
                }
                else if (region != null && region.Equals("eu", StringComparison.OrdinalIgnoreCase))
                {
                    rate += 0.015;
                }
                else if (region != null && region.Equals("apac", StringComparison.OrdinalIgnoreCase))
                {
                    rate += 0.01;
                }
                else
                {
                    rate += 0.005;
                }
            }

            if (hasCoupon)
            {
                if (orderTotalCents < 5000)
                {
                    rate += 0.01;
                }
                else if (orderTotalCents < 15000)
                {
                    rate += 0.02;
                }
                else
                {
                    rate += 0.03;
                }
            }

            if (rate > 0.30)
            {
                rate = 0.30;
            }
            if (rate < 0.0)
            {
                rate = 0.0;
            }
            return rate;
        }

        public static string SummarizeLineItem(string? sku, int qty, int unitPriceCents)
        {
            string prefix;
            if (sku == null || string.IsNullOrWhiteSpace(sku))
            {
                prefix = "UNKNOWN";
            }
            else if (sku.StartsWith("DIG-"))
            {
                if (qty > 1)
                {
                    if (unitPriceCents > 999)
                    {
                        prefix = "DIG-BULK-HIGH";
                    }
                    else if (unitPriceCents > 199)
                    {
                        prefix = "DIG-BULK-MID";
                    }
                    else
                    {
                        prefix = "DIG-BULK-LOW";
                    }
                }
                else
                {
                    prefix = "DIG-SINGLE";
                }
            }
            else if (sku.StartsWith("PHY-"))
            {
                prefix = qty > 5 ? "PHY-BULK" : "PHY-STD";
            }
            else
            {
                prefix = "GEN";
            }

            int lineTotal = qty * unitPriceCents;
            if (lineTotal < 0)
            {
                lineTotal = 0;
            }
            return prefix + ":" + lineTotal.ToString();
        }
    }
}
