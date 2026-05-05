namespace ComplexitySample;

/// <summary>
/// Near-duplicate of <see cref="DiscountCalculator"/> logic to surface code duplication in analysis tools.
/// </summary>
public static class TaxCalculator
{
    public static double ComputeTieredSurcharge(
        string? customerTier,
        int orderTotalCents,
        int itemCount,
        bool isHoliday,
        bool hasCoupon,
        string? region)
    {
        double rate = 0.0;
        if (customerTier is null)
        {
            rate = 0.0;
        }
        else if (string.Equals(customerTier, "GOLD", StringComparison.OrdinalIgnoreCase))
        {
            if (orderTotalCents > 500_00)
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
            else if (orderTotalCents > 200_00)
            {
                rate = itemCount > 3 ? 0.10 : 0.08;
            }
            else
            {
                rate = 0.05;
            }
        }
        else if (string.Equals(customerTier, "SILVER", StringComparison.OrdinalIgnoreCase))
        {
            rate = orderTotalCents > 300_00 ? 0.08 : 0.04;
        }
        else if (string.Equals(customerTier, "BRONZE", StringComparison.OrdinalIgnoreCase))
        {
            rate = orderTotalCents > 150_00 ? 0.03 : 0.01;
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
            if (string.Equals(region, "US", StringComparison.OrdinalIgnoreCase))
            {
                rate += 0.02;
            }
            else if (string.Equals(region, "EU", StringComparison.OrdinalIgnoreCase))
            {
                rate += 0.015;
            }
            else if (string.Equals(region, "APAC", StringComparison.OrdinalIgnoreCase))
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
            if (orderTotalCents < 50_00)
            {
                rate += 0.01;
            }
            else if (orderTotalCents < 150_00)
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

    public static string SummarizePhysicalLine(string? sku, int qty, int unitPriceCents)
    {
        string prefix;
        if (string.IsNullOrWhiteSpace(sku))
        {
            prefix = "UNKNOWN";
        }
        else if (sku.StartsWith("DIG-", StringComparison.Ordinal))
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
        else if (sku.StartsWith("PHY-", StringComparison.Ordinal))
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

        return prefix + ":" + lineTotal;
    }
}
