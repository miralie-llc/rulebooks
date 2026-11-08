import { spawnSync, spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const [command = "build", ...args] = process.argv.slice(2);
if (!["dev", "build"].includes(command)) throw new Error("Use dev or build.");
const prepareArgs = ["tools/prepare_site.py"];
const astroArgs = [];
for (let i = 0; i < args.length; i++) {
  if (["--publication", "--digest", "--catalog"].includes(args[i])) {
    if (!args[i + 1]) throw new Error("Missing data argument.");
    prepareArgs.push(args[i], args[++i]);
  } else astroArgs.push(args[i]);
}
const prepared = spawnSync(
  process.env.RULEBOOKS_PYTHON || "python3",
  prepareArgs,
  { cwd: root, stdio: "inherit" },
);
if (prepared.status !== 0) process.exit(prepared.status || 1);
const child = spawn(
  process.execPath,
  [path.join(root, "node_modules/astro/bin/astro.mjs"), command, ...astroArgs],
  {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, ASTRO_TELEMETRY_DISABLED: "1" },
  },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("error", () => process.exit(1));
child.on("exit", (code) => process.exit(code ?? 1));
