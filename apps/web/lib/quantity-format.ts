"use client";

export function formatQuantityValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "";
  }

  const stringValue = String(value).trim();
  if (!stringValue) {
    return "";
  }

  if (!/^-?\d+(?:\.\d+)?$/.test(stringValue)) {
    return stringValue;
  }

  const [whole, fraction = ""] = stringValue.split(".");
  const trimmedFraction = fraction.replace(/0+$/, "");
  return trimmedFraction ? `${whole}.${trimmedFraction}` : whole;
}


export function formatQuantityWithUnit(
  quantity: string | number | null | undefined,
  unit: string | null | undefined,
  emptyLabel = "No quantity set"
): string {
  const formattedQuantity = formatQuantityValue(quantity);
  if (!formattedQuantity) {
    return emptyLabel;
  }
  if (!unit) {
    return formattedQuantity;
  }
  return `${formattedQuantity} ${unit}`;
}
