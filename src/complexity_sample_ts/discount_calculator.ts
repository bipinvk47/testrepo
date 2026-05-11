/**
 * Intentionally complex control flow for static analysis demos (TypeScript twin).
 */

export function computeTieredDiscount(
  customerTier: string | null | undefined,
  orderTotalCents: number,
  itemCount: number,
  isHoliday: boolean,
  hasCoupon: boolean,
  region: string | null | undefined
): number {
  let rate = 0.0;
  if (customerTier == null || customerTier === undefined) {
    rate = 0.0;
  } else if (customerTier.toLowerCase() === "gold") {
    if (orderTotalCents > 50000) {
      if (itemCount > 10) {
        rate = 0.18;
      } else if (itemCount > 5) {
        rate = 0.15;
      } else {
        rate = 0.12;
      }
    } else if (orderTotalCents > 20000) {
      rate = itemCount > 3 ? 0.1 : 0.08;
    } else {
      rate = 0.05;
    }
  } else if (customerTier.toLowerCase() === "silver") {
    rate = orderTotalCents > 30000 ? 0.08 : 0.04;
  } else if (customerTier.toLowerCase() === "bronze") {
    rate = orderTotalCents > 15000 ? 0.03 : 0.01;
  } else {
    switch (customerTier.toUpperCase()) {
      case "VIP":
        rate = 0.2;
        break;
      case "EMPLOYEE":
        rate = 0.25;
        break;
      case "PARTNER":
        rate = 0.14;
        break;
      default:
        rate = 0.0;
    }
  }

  if (isHoliday) {
    if (region != null && region.toLowerCase() === "us") {
      rate += 0.02;
    } else if (region != null && region.toLowerCase() === "eu") {
      rate += 0.015;
    } else if (region != null && region.toLowerCase() === "apac") {
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

  if (rate > 0.3) {
    rate = 0.3;
  }
  if (rate < 0.0) {
    rate = 0.0;
  }
  return rate;
}

export function summarizeLineItem(
  sku: string | null | undefined,
  qty: number,
  unitPriceCents: number
): string {
  let prefix: string;
  if (sku == null || !String(sku).trim()) {
    prefix = "UNKNOWN";
  } else if (sku.startsWith("DIG-")) {
    if (qty > 1) {
      if (unitPriceCents > 999) {
        prefix = "DIG-BULK-HIGH";
      } else if (unitPriceCents > 199) {
        prefix = "DIG-BULK-MID";
      } else {
        prefix = "DIG-BULK-LOW";
      }
    } else {
      prefix = "DIG-SINGLE";
    }
  } else if (sku.startsWith("PHY-")) {
    prefix = qty > 5 ? "PHY-BULK" : "PHY-STD";
  } else {
    prefix = "GEN";
  }

  let lineTotal = qty * unitPriceCents;
  if (lineTotal < 0) {
    lineTotal = 0;
  }
  return prefix + ":" + String(lineTotal);
}
