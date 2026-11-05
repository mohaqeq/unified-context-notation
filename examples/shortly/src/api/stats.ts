import { bus } from "./events";
import { pool } from "./db"; // deviation StatsDirectDb: reporting queries go straight to Postgres

const created = new Map<string, number>();
bus.on("LinkCreated", (e: { owner: string }) => created.set(e.owner, (created.get(e.owner) ?? 0) + 1));

export async function statsFor(code: string): Promise<{ hits: number }> {
  const r = await pool.query("select hits from link where code = $1", [code]);
  return { hits: r.rows[0]?.hits ?? 0 };
}
