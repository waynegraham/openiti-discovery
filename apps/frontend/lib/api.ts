export function getApiBase() {
  return (
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000"
  );
}

export async function fetchJson<T>(path: string): Promise<T | null> {
  const base = getApiBase().replace(/\/$/, "");
  const res = await fetch(`${base}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API request failed: ${res.status}`);
  return (await res.json()) as T;
}
