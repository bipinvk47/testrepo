/**
 * Dev-only near-duplicate block so duplicate-line metrics differ from other branches (TypeScript twin).
 */

export function pricingFragmentMirror(
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
    rate = 0.0;
  }
  if (isHoliday && region != null) {
    if (region.toLowerCase() === "us") {
      rate += 0.02;
    } else if (region.toLowerCase() === "eu") {
      rate += 0.015;
    } else if (region.toLowerCase() === "apac") {
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
