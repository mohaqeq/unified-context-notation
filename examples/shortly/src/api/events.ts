import { EventEmitter } from "node:events";

export type LinkCreated = { code: string; owner: string };
export const bus = new EventEmitter();

export function publishLinkCreated(e: LinkCreated): void {
  bus.emit("LinkCreated", e);
}
