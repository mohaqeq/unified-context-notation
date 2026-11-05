import { generate } from "./codes";
import { check, limit } from "./guard";
import { insertLink, findLink } from "./db";
import { getTarget, putTarget } from "./cache";
import { publishLinkCreated } from "./events";

export function isHttpUrl(url: string): boolean {
  return /^https?:\/\//.test(url);
}

export async function create(url: string, owner: string): Promise<string> {
  if (!isHttpUrl(url)) throw Object.assign(new Error("invalid url"), { status: 400 });
  limit(owner);
  await check(url);
  const code = await generate();
  await insertLink(code, url, owner);
  publishLinkCreated({ code, owner });
  return code;
}

export async function resolve(code: string): Promise<string> {
  const cached = await getTarget(code);
  if (cached) return cached;
  const link = await findLink(code);
  if (!link) throw Object.assign(new Error("unknown code"), { status: 404 });
  if (link.expiresAt && link.expiresAt < new Date()) throw Object.assign(new Error("expired"), { status: 410 });
  await putTarget(code, link.target, 3600);
  return link.target;
}
