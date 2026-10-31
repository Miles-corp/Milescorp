// Écrit `dist/build-info.json` avec une empreinte des sources.
//
// L'empreinte est recalculée côté Python par `tests/test_companion_dist.py`.
// Toute modification de source sans rebuild fait donc échouer la suite : c'est
// le garde-fou contre un `dist/` périmé livré sur la box (qui n'a pas Node).
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const dist = join(root, "..", "dist");

const FIXED = ["index.html", "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts"];

function walk(directory) {
  const entries = [];
  for (const name of readdirSync(directory)) {
    const full = join(directory, name);
    const info = statSync(full);
    if (info.isDirectory()) entries.push(...walk(full));
    else entries.push(full);
  }
  return entries;
}

const files = [];
for (const name of FIXED) {
  const full = join(root, name);
  if (existsSync(full)) files.push(full);
}
files.push(...walk(join(root, "src")));

const unique = [...new Set(files)].sort((a, b) =>
  relative(root, a).split(sep).join("/").localeCompare(relative(root, b).split(sep).join("/")),
);

const hash = createHash("sha256");
let bytes = 0;
for (const full of unique) {
  const rel = relative(root, full).split(sep).join("/");
  const data = readFileSync(full);
  bytes += data.length;
  hash.update(rel + "\n");
  hash.update(createHash("sha256").update(data).digest("hex"));
  hash.update("\n");
}

let viteVersion = "inconnue";
try {
  viteVersion = JSON.parse(readFileSync(join(root, "node_modules", "vite", "package.json"), "utf8")).version;
} catch {
  // build sans node_modules complets : la version reste déclarative
}

const info = {
  source_hash: hash.digest("hex"),
  source_files: unique.length,
  source_bytes: bytes,
  built_at: new Date().toISOString(),
  node: process.version,
  vite: viteVersion,
};

writeFileSync(join(dist, "build-info.json"), JSON.stringify(info, null, 2) + "\n", "utf8");
console.log("[build-info] %s fichiers, empreinte %s", info.source_files, info.source_hash.slice(0, 16));
