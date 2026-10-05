const { python, root, run } = require("./python.cjs");
const { join } = require("node:path");
const requested = process.argv[2];
for (const flag of ["--x64", "--arm64", "--ia32", "--universal"]) {
  if (process.argv.includes(flag) && flag !== "--" + process.arch)
    throw new Error("App und Python-Laufzeit müssen auf derselben Zielarchitektur gebaut werden.");
}
const platform =
  process.platform === "darwin"
    ? "mac"
    : process.platform === "win32"
      ? "win"
      : "linux";
if (requested !== platform)
  throw new Error(
    "Die Python-Laufzeit muss auf dem Zielsystem gebaut werden. Bitte den " +
      requested +
      "-Build dort oder über den macOS-Workflow starten.",
  );
run(process.execPath, [
  join(root, "node_modules/typescript/bin/tsc"),
  "--noEmit",
]);
run(process.execPath, [join(root, "node_modules/vite/bin/vite.js"), "build"]);
run(python, ["scripts/build_backend.py", "--expected-arch", process.arch]);
run(process.execPath, [
  join(root, "node_modules/electron-builder/out/cli/cli.js"),
  "--" + platform,
  "--" + process.arch,
  ...process.argv.slice(3),
  "--publish",
  "never",
]);
