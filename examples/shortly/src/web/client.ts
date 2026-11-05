export async function shorten(url: string): Promise<string> {
  const res = await fetch("/links", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ url }) });
  return (await res.json()).code;
}
