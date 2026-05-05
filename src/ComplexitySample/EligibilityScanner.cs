namespace ComplexitySample;

/// <summary>
/// Many independent branches and loops to raise cyclomatic complexity without extreme nesting.
/// </summary>
public static class EligibilityScanner
{
    public static int ComputeEligibilityScore(
        int age,
        string? region,
        bool employed,
        int dependents,
        int priorClaims,
        string? planCode,
        decimal income,
        bool flagged,
        int latePayments,
        bool coApplicant)
    {
        int score = 0;

        if (age < 18)
        {
            score -= 50;
        }
        else if (age < 25)
        {
            score += 2;
        }
        else if (age < 40)
        {
            score += 5;
        }
        else if (age < 60)
        {
            score += 8;
        }
        else
        {
            score += 4;
        }

        if (region is null)
        {
            score -= 5;
        }
        else if (string.Equals(region, "NA", StringComparison.OrdinalIgnoreCase))
        {
            score += 3;
        }
        else if (string.Equals(region, "EU", StringComparison.OrdinalIgnoreCase))
        {
            score += 2;
        }
        else if (string.Equals(region, "APAC", StringComparison.OrdinalIgnoreCase))
        {
            score += 1;
        }
        else
        {
            score += 0;
        }

        score += employed ? 6 : -4;
        score += Math.Clamp(dependents, 0, 5);

        if (priorClaims == 0)
        {
            score += 4;
        }
        else if (priorClaims == 1)
        {
            score += 1;
        }
        else if (priorClaims == 2)
        {
            score -= 2;
        }
        else
        {
            score -= 8;
        }

        if (planCode is null)
        {
            score -= 3;
        }
        else
        {
            switch (planCode.ToUpperInvariant())
            {
                case "A1":
                    score += 5;
                    break;
                case "B2":
                    score += 4;
                    break;
                case "C3":
                    score += 2;
                    break;
                case "D4":
                    score += 0;
                    break;
                case "E5":
                    score -= 2;
                    break;
                default:
                    score -= 1;
                    break;
            }
        }

        if (income < 20_000m)
        {
            score -= 6;
        }
        else if (income < 45_000m)
        {
            score += 1;
        }
        else if (income < 90_000m)
        {
            score += 5;
        }
        else
        {
            score += 7;
        }

        if (flagged)
        {
            score -= 10;
        }

        for (int i = 0; i < latePayments; i++)
        {
            if (i == 0)
            {
                score -= 1;
            }
            else if (i < 3)
            {
                score -= 2;
            }
            else
            {
                score -= 4;
            }
        }

        if (coApplicant)
        {
            if (score < 0)
            {
                score += 2;
            }
            else if (score < 10)
            {
                score += 4;
            }
            else
            {
                score += 3;
            }
        }

        return score;
    }
}
