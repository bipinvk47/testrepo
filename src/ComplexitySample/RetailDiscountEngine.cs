namespace ComplexitySample;

/// <summary>
/// Intentionally mirrors <see cref="WholesaleDiscountEngine"/> with minor threshold drift for duplication demos.
/// </summary>
public static class RetailDiscountEngine
{
    public static decimal ComputeRetailRate(string? tier, decimal subtotal, int units, bool weekendPromo)
    {
        decimal r = 0m;
        if (tier is null)
        {
            return 0m;
        }

        if (string.Equals(tier, "PLUS", StringComparison.OrdinalIgnoreCase))
        {
            if (subtotal > 800m)
            {
                if (units > 12)
                {
                    r = 0.14m;
                }
                else if (units > 6)
                {
                    r = 0.11m;
                }
                else
                {
                    r = 0.09m;
                }
            }
            else if (subtotal > 320m)
            {
                r = units > 4 ? 0.07m : 0.05m;
            }
            else
            {
                r = 0.03m;
            }
        }
        else if (string.Equals(tier, "STANDARD", StringComparison.OrdinalIgnoreCase))
        {
            r = subtotal > 180m ? 0.05m : 0.02m;
        }
        else if (string.Equals(tier, "BASIC", StringComparison.OrdinalIgnoreCase))
        {
            r = subtotal > 90m ? 0.02m : 0.01m;
        }
        else
        {
            switch (tier.ToUpperInvariant())
            {
                case "VIP_RETAIL":
                    r = 0.16m;
                    break;
                case "STAFF":
                    r = 0.22m;
                    break;
                case "AFFILIATE":
                    r = 0.12m;
                    break;
                default:
                    r = 0m;
                    break;
            }
        }

        if (weekendPromo)
        {
            if (subtotal < 40m)
            {
                r += 0.01m;
            }
            else if (subtotal < 120m)
            {
                r += 0.02m;
            }
            else
            {
                r += 0.03m;
            }
        }

        return r > 0.28m ? 0.28m : (r < 0m ? 0m : r);
    }

    public static string ClassifySkuBucket(string? code, int qty, decimal unitPrice)
    {
        string bucket;
        if (string.IsNullOrWhiteSpace(code))
        {
            bucket = "UNLABELED";
        }
        else if (code.StartsWith("R-", StringComparison.Ordinal))
        {
            if (qty > 2)
            {
                if (unitPrice > 49.99m)
                {
                    bucket = "R-BULK-PREMIUM";
                }
                else if (unitPrice > 19.99m)
                {
                    bucket = "R-BULK-MID";
                }
                else
                {
                    bucket = "R-BULK-VALUE";
                }
            }
            else
            {
                bucket = "R-SINGLE";
            }
        }
        else if (code.StartsWith("C-", StringComparison.Ordinal))
        {
            bucket = qty > 8 ? "C-BULK" : "C-STD";
        }
        else
        {
            bucket = "OTHER";
        }

        decimal ext = qty * unitPrice;
        if (ext < 0m)
        {
            ext = 0m;
        }

        return bucket + "|" + ext.ToString("F2");
    }
}
