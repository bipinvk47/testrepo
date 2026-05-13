// Sample complex control flow for static analysis demos (Go twin).
package complexitysample

import (
	"strconv"
	"strings"
)

func ComputeTieredDiscount(
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
		switch strings.ToUpper(customerTier) {
		case "VIP":
			rate = 0.20
		case "EMPLOYEE":
			rate = 0.25
		case "PARTNER":
			rate = 0.14
		default:
			rate = 0.0
		}
	}

	if isHoliday {
		if region != "" && strings.EqualFold(region, "us") {
			rate += 0.02
		} else if region != "" && strings.EqualFold(region, "eu") {
			rate += 0.015
		} else if region != "" && strings.EqualFold(region, "apac") {
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

func SummarizeLineItem(sku string, qty int, unitPriceCents int) string {
	prefix := ""
	if sku == "" || strings.TrimSpace(sku) == "" {
		prefix = "UNKNOWN"
	} else if strings.HasPrefix(sku, "DIG-") {
		if qty > 1 {
			if unitPriceCents > 999 {
				prefix = "DIG-BULK-HIGH"
			} else if unitPriceCents > 199 {
				prefix = "DIG-BULK-MID"
			} else {
				prefix = "DIG-BULK-LOW"
			}
		} else {
			prefix = "DIG-SINGLE"
		}
	} else if strings.HasPrefix(sku, "PHY-") {
		if qty > 5 {
			prefix = "PHY-BULK"
		} else {
			prefix = "PHY-STD"
		}
	} else {
		prefix = "GEN"
	}

	lineTotal := qty * unitPriceCents
	if lineTotal < 0 {
		lineTotal = 0
	}
	return prefix + ":" + strconv.Itoa(lineTotal)
}
