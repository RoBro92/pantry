export function looksLikeEmailAddress(value: string | null | undefined): boolean {
  if (!value) {
    return false;
  }
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
