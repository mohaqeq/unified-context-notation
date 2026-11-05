import { codeExists } from "./db";

export const CODE_LENGTH = 7;
const ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

export async function generate(): Promise<string> {
  for (let attempt = 0; attempt < 5; attempt++) {
    let code = "";
    for (let i = 0; i < CODE_LENGTH; i++) code += ALPHABET[Math.floor(Math.random() * ALPHABET.length)];
    if (!(await codeExists(code))) return code;
  }
  throw Object.assign(new Error("could not generate a free code"), { status: 503 });
}
