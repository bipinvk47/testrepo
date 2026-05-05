namespace ComplexitySample;

/// <summary>
/// Deep nesting and many paths to increase cognitive complexity in one place.
/// </summary>
public static class LegacyApprovalRouter
{
    public static int Route(string? dept, int amountCents, bool urgent, bool weekend, int retries)
    {
        int level = 0;
        if (dept is not null)
        {
            if (string.Equals(dept, "FINANCE", StringComparison.OrdinalIgnoreCase))
            {
                if (amountCents > 1_000_000)
                {
                    if (urgent)
                    {
                        if (!weekend)
                        {
                            if (retries < 3)
                            {
                                level = 4;
                            }
                            else
                            {
                                level = 5;
                            }
                        }
                        else
                        {
                            if (retries == 0)
                            {
                                level = 3;
                            }
                            else
                            {
                                level = 4;
                            }
                        }
                    }
                    else
                    {
                        level = amountCents > 5_000_000 ? 5 : 3;
                    }
                }
                else if (amountCents > 250_000)
                {
                    level = urgent ? 3 : 2;
                }
                else
                {
                    level = 1;
                }
            }
            else if (string.Equals(dept, "HR", StringComparison.OrdinalIgnoreCase))
            {
                level = amountCents > 50_000 ? 2 : 1;
            }
            else if (string.Equals(dept, "IT", StringComparison.OrdinalIgnoreCase))
            {
                for (int i = 0; i < retries; i++)
                {
                    if (amountCents > 200_000 && urgent)
                    {
                        level = Math.Max(level, 3);
                    }
                    else if (amountCents > 80_000)
                    {
                        level = Math.Max(level, 2);
                    }
                    else
                    {
                        level = Math.Max(level, 1);
                    }
                }
            }
            else
            {
                level = amountCents > 10_000 ? 2 : 1;
            }
        }

        return level;
    }
}
