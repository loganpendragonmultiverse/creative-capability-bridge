import { readFile } from "node:fs/promises";

const html = await readFile("site/index.html", "utf8");
for (const expected of ["id=\"builder\"", "id=\"roadmap\"", "app.js", "styles.css"]) {
  if (!html.includes(expected)) throw new Error(`Missing site marker: ${expected}`);
}
if ((html.match(/<h1/g) || []).length !== 1) throw new Error("Site must contain exactly one h1.");
process.stdout.write("Site structure checks passed.\n");

