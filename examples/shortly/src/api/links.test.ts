import { create } from "./links";

test("create returns 7 chars", async () => {
  expect(await create("https://example.com", "u1")).toHaveLength(7);
});

test("the same URL twice gets two different codes", async () => {
  expect(await create("https://example.com", "u1")).not.toEqual(await create("https://example.com", "u1"));
});
