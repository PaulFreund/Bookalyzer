const { existsSync } = require("node:fs");
const { join, resolve } = require("node:path");
const { spawnSync } = require("node:child_process");
const root = resolve(__dirname, "..");
const local = join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python =
  process.env.BOOKANALYZER_PYTHON ||
  (existsSync(local)
    ? local
    : process.platform === "win32"
      ? "python"
      : "python3");
function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    windowsHide: true,
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0)
    throw new Error(command + " exited with " + result.status);
}
if (require.main === module) {
  try {
    run(python, process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
module.exports = { python, root, run };
