const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const PKG_ROOT = path.resolve(HERE, "..");
const MONOREPO_ROOT = path.resolve(PKG_ROOT, "..", "..");
const CSRC_DIR = path.join(PKG_ROOT, "csrc");

const VENDOR_DIRS = ["src", "include", "lib/yyjson", "lib/libb64"];

const IGNORE = [".o", ".obj", ".d", ".DS_Store", "main.c", "capture.h"];

function shouldIgnore(name) {
  return IGNORE.some((pattern) => name.endsWith(pattern) || name === pattern);
}

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (shouldIgnore(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "build") continue;
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

if (fs.existsSync(CSRC_DIR)) {
  process.exit(0);
}

for (const relDir of VENDOR_DIRS) {
  const srcPath = path.join(MONOREPO_ROOT, relDir);
  const destPath = path.join(CSRC_DIR, relDir);
  if (fs.existsSync(srcPath)) {
    copyDirSync(srcPath, destPath);
  }
}

const DATA_SRC = path.join(MONOREPO_ROOT, "data");
const DATA_DEST = path.join(PKG_ROOT, "data");
if (fs.existsSync(DATA_SRC) && !fs.existsSync(DATA_DEST)) {
  copyDirSync(DATA_SRC, DATA_DEST);
}
