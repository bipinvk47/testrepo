namespace ComplexitySample;

/// <summary>
/// Near-duplicate of <see cref="RetailDiscountEngine"/> (different literals, same structure) for duplication analysis.
/// </summary>
public static class WholesaleDiscountEngine
{
    public static decimal ComputeWholesaleRate(string? tier, decimal subtotal, int units, bool weekendPromo)
    {
        decimal r = 0m;
        if (tier is null)
        {
            return 0m;
        }

        if (string.Equals(tier, "PLUS", StringComparison.OrdinalIgnoreCase))
        {
            if (subtotal > 750m)
            {
                if (units > 10)
                {
                    r = 0.14m;
                }
                else if (units > 5)
                {
                    r = 0.11m;
                }
                else
                {
                    r = 0.09m;
                }
            }
            else if (subtotal > 300m)
            {
                r = units > 3 ? 0.07m : 0.05m;
            }
            else
            {
                r = 0.03m;
            }
        }
        else if (string.Equals(tier, "STANDARD", StringComparison.OrdinalIgnoreCase))
        {
            r = subtotal > 200m ? 0.05m : 0.02m;
        }
        else if (string.Equals(tier, "BASIC", StringComparison.OrdinalIgnoreCase))
        {
            r = subtotal > 100m ? 0.02m : 0.01m;
        }
        else
        {
            switch (tier.ToUpperInvariant())
            {
                case "VIP_WHOLESALE":
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
            if (subtotal < 50m)
            {
                r += 0.01m;
            }
            else if (subtotal < 130m)
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
        else if (code.StartsWith("W-", StringComparison.Ordinal))
        {
            if (qty > 2)
            {
                if (unitPrice > 44.99m)
                {
                    bucket = "W-BULK-PREMIUM";
                }
                else if (unitPrice > 17.99m)
                {
                    bucket = "W-BULK-MID";
                }
                else
                {
                    bucket = "W-BULK-VALUE";
                }
            }
            else
            {
                bucket = "W-SINGLE";
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
