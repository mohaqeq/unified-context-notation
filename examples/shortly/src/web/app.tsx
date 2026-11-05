import { ALIASES_ENABLED } from "../api/config"; // legacy: the UI reads a server flag at build time

export function CreateForm() {
  return (
    <form method="post" action="/links">
      <input name="url" placeholder="https://..." />
      {ALIASES_ENABLED && <input name="alias" placeholder="custom alias" />}
      <button>Shorten</button>
    </form>
  );
}
