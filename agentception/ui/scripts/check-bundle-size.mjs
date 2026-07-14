import { readdir, stat } from "node:fs/promises";
import path from "node:path";

const limitBytes = 400 * 1024;
const assetsDirectory = path.resolve("dist", "assets");
const files = (await readdir(assetsDirectory)).filter((file) => file.endsWith(".js"));
const oversized = [];

for (const file of files) {
  const size = (await stat(path.join(assetsDirectory, file))).size;
  if (size > limitBytes) oversized.push(`${file}: ${size} bytes`);
}

if (oversized.length > 0) {
  throw new Error(`JavaScript bundle budget exceeded (${limitBytes} bytes):\n${oversized.join("\n")}`);
}

console.log(`Bundle budget passed for ${files.length} JavaScript chunks.`);
