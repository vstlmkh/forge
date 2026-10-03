#!/usr/bin/env node
// npm entry point. The CLI itself is Python - stdlib only, like the harness it
// installs - so this is a shim and nothing more: find an interpreter, hand it
// bin/forge, forward argv and the exit code.
"use strict";

const { spawnSync } = require("node:child_process");
const { join } = require("node:path");

const cli = join(__dirname, "forge");
const args = process.argv.slice(2);

for (const python of ["python3", "python"]) {
  const run = spawnSync(python, [cli, ...args], { stdio: "inherit" });

  if (run.error) {
    if (run.error.code === "ENOENT") continue; // not this one; try the next
    console.error(`forge: could not run ${python}: ${run.error.message}`);
    process.exit(1);
  }
  // a child killed by a signal has a null status; report it as a failure
  process.exit(run.status === null ? 1 : run.status);
}

console.error(
  "forge needs Python 3.9 or newer on your PATH, and found neither `python3` " +
    "nor `python`.\n" +
    "  macOS:  brew install python\n" +
    "  Debian: sudo apt install python3\n" +
    "Nothing else is required - forge has no runtime dependencies."
);
process.exit(1);
