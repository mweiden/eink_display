import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { findSystemChromiumExecutable } from "./browser_launcher.js";

function createFakeBinary(name) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "chromium-bin-"));
  const binaryPath = path.join(tempDir, name);
  fs.writeFileSync(binaryPath, "#!/bin/sh\nexit 0\n", { mode: 0o755 });
  fs.chmodSync(binaryPath, 0o755);
  return { tempDir, binaryPath };
}

test("findSystemChromiumExecutable returns first executable in PATH candidates", (t) => {
  const { tempDir, binaryPath } = createFakeBinary("chromium");
  t.after(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  const resolved = findSystemChromiumExecutable({
    absoluteCandidates: [],
    pathCandidates: ["chromium"],
    envPath: `${tempDir}${path.delimiter}/nonexistent`,
  });
  assert.equal(resolved, binaryPath);
});

test("findSystemChromiumExecutable returns null when no browser is available", () => {
  const resolved = findSystemChromiumExecutable({
    absoluteCandidates: [],
    pathCandidates: ["chromium"],
    envPath: "/nonexistent",
  });
  assert.equal(resolved, null);
});
