import { isHttpUrl } from "./links"; // erosion: Guard reaches into Links for a helper

export const LIMIT_PER_HOUR = 1000;
const recent = new Map<string, number[]>();

export async function check(url: string): Promise<void> {
  if (!isHttpUrl(url)) return;
  const res = await fetch("https://safebrowsing.example/v4/lookup", { method: "POST", body: JSON.stringify({ url }) });
  if ((await res.json()).blocked) throw Object.assign(new Error("blocked domain"), { status: 422 });
}

export function limit(owner: string): void {
  const hourAgo = Date.now() - 3600_000;
  const times = (recent.get(owner) ?? []).filter((t) => t > hourAgo);
  if (times.length >= LIMIT_PER_HOUR) throw Object.assign(new Error("rate limited"), { status: 429 });
  recent.set(owner, [...times, Date.now()]);
}
