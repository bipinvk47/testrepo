using System;

namespace ComplexitySample
{
    public static class CopyPastePricingFragment
    {
        public static double PricingFragmentMirror(
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
                rate = 0.0;
            }
            if (isHoliday && region != null)
            {
                if (region.Equals("us", StringComparison.OrdinalIgnoreCase))
                {
                    rate += 0.02;
                }
                else if (region.Equals("eu", StringComparison.OrdinalIgnoreCase))
                {
                    rate += 0.015;
                }
                else if (region.Equals("apac", StringComparison.OrdinalIgnoreCase))
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
    }
}
