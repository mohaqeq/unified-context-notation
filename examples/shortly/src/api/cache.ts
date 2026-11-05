import { createClient } from "redis";

const redis = createClient();

export async function getTarget(code: string): Promise<string | null> {
  return redis.get(`code:${code}`);
}

export async function putTarget(code: string, target: string, ttlSeconds: number): Promise<void> {
  await redis.set(`code:${code}`, target, { EX: ttlSeconds });
}
