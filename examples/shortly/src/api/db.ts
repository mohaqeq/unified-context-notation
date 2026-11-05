// The only module that talks to Postgres (convention DbAccess).
import { Pool } from "pg";

export const pool = new Pool();

export async function insertLink(code: string, target: string, owner: string): Promise<void> {
  await pool.query("insert into link(code, target, owner, created_at) values ($1, $2, $3, now())", [code, target, owner]);
}

export async function findLink(code: string): Promise<{ target: string; expiresAt: Date | null } | null> {
  const r = await pool.query("select target, expires_at from link where code = $1 and not disabled", [code]);
  return r.rows[0] ? { target: r.rows[0].target, expiresAt: r.rows[0].expires_at } : null;
}

export async function codeExists(code: string): Promise<boolean> {
  const r = await pool.query("select 1 from link where code = $1", [code]);
  return r.rowCount > 0;
}
