import { limit, LIMIT_PER_HOUR } from "./guard";

test("the 1001st link in an hour gets 429", () => {
  expect(LIMIT_PER_HOUR).toBe(1000);
  for (let i = 0; i < 1000; i++) limit("u2");
  expect(() => limit("u2")).toThrow("rate limited");
});
