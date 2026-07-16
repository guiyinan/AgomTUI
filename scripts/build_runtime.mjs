import { build } from "esbuild";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const entry = resolve(root, "packages/agomtui-runtime/frontend/src/index.js");
const outfile = resolve(root, "packages/agomtui-runtime/reference/static/js/agomtui-runtime-core.js");
const check = process.argv.includes("--check");
const result = await build({
    entryPoints: [entry],
    bundle: true,
    format: "iife",
    platform: "browser",
    target: ["es2020"],
    minify: true,
    sourcemap: false,
    write: false,
    outfile,
});
const expected = Buffer.from(result.outputFiles[0].contents);

if (check) {
    const current = await readFile(outfile).catch(() => Buffer.alloc(0));
    if (!current.equals(expected)) {
        throw new Error(`Downstream Runtime bundle drifted from synchronized source: ${outfile}`);
    }
} else {
    await writeFile(outfile, expected);
}
