export const toSafeExternalUrl = (value: string | null | undefined): string | null => {
  if (!value) return null;

  try {
    const url = new URL(value);
    if (!(["http:", "https:"] as const).includes(url.protocol as "http:" | "https:")) return null;
    if (url.username || url.password) return null;
    return url.toString();
  } catch {
    return null;
  }
};
