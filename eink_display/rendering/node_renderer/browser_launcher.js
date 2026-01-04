import fs from "node:fs";
import path from "node:path";

const DEFAULT_ABSOLUTE_CANDIDATES = [
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
  "/usr/bin/chromium-headless-shell",
  "/usr/lib/chromium/chromium-headless-shell",
  "/snap/bin/chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
];

const DEFAULT_PATH_CANDIDATES = [
  "chromium-browser",
  "chromium",
  "chromium-headless-shell",
  "google-chrome",
  "google-chrome-stable",
  "chrome",
];

function isExecutable(filePath) {
  if (!filePath) {
    return false;
  }
  try {
    const stats = fs.statSync(filePath);
    if (!stats.isFile()) {
      return false;
    }
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function expandPathCandidates(envPath, candidates) {
  if (!envPath) {
    return [];
  }
  const entries = envPath.split(path.delimiter).filter(Boolean);
  const locations = [];
  for (const entry of entries) {
    for (const name of candidates) {
      locations.push(path.join(entry, name));
    }
  }
  return locations;
}

export function findSystemChromiumExecutable(options = {}) {
  const {
    absoluteCandidates = DEFAULT_ABSOLUTE_CANDIDATES,
    pathCandidates = DEFAULT_PATH_CANDIDATES,
    envPath = process.env.PATH || "",
  } = options;

  const searchOrder = [...absoluteCandidates, ...expandPathCandidates(envPath, pathCandidates)];
  const seen = new Set();
  for (const location of searchOrder) {
    if (seen.has(location)) {
      continue;
    }
    seen.add(location);
    if (isExecutable(location)) {
      return location;
    }
  }
  return null;
}
