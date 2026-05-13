// Near-duplicate pricing block for duplication metrics (Go twin).
package complexitysample

import "strings"

func PricingFragmentMirror(
	customerTier string,
	orderTotalCents int,
	itemCount int,
	isHoliday bool,
	hasCoupon bool,
	region string,
) float64 {
	rate := 0.0
	if customerTier == "" {
		rate = 0.0
	} else if strings.EqualFold(customerTier, "gold") {
		if orderTotalCents > 50000 {
			if itemCount > 10 {
				rate = 0.18
			} else if itemCount > 5 {
				rate = 0.15
			} else {
				rate = 0.12
			}
		} else if orderTotalCents > 20000 {
			if itemCount > 3 {
				rate = 0.10
			} else {
				rate = 0.08
			}
		} else {
			rate = 0.05
		}
	} else if strings.EqualFold(customerTier, "silver") {
		if orderTotalCents > 30000 {
			rate = 0.08
		} else {
			rate = 0.04
		}
	} else if strings.EqualFold(customerTier, "bronze") {
		if orderTotalCents > 15000 {
			rate = 0.03
		} else {
			rate = 0.01
		}
	} else {
		rate = 0.0
	}
	if isHoliday && region != "" {
		if strings.EqualFold(region, "us") {
			rate += 0.02
		} else if strings.EqualFold(region, "eu") {
			rate += 0.015
		} else if strings.EqualFold(region, "apac") {
			rate += 0.01
		} else {
			rate += 0.005
		}
	}
	if hasCoupon {
		if orderTotalCents < 5000 {
			rate += 0.01
		} else if orderTotalCents < 15000 {
			rate += 0.02
		} else {
			rate += 0.03
		}
	}
	if rate > 0.30 {
		rate = 0.30
	}
	if rate < 0.0 {
		rate = 0.0
	}
	return rate
}
