"use strict";

const fs = require("node:fs");
const path = require("node:path");
const validator = require("gltf-validator");

async function main() {
  if (process.argv.length !== 3) {
    throw new Error("Usage: node validate.cjs ASSET.glb");
  }
  const filename = path.resolve(process.argv[2]);
  const report = await validator.validateBytes(new Uint8Array(fs.readFileSync(filename)), {
    uri: path.basename(filename),
    format: "glb",
    writeTimestamp: false,
    maxIssues: 0,
    severityOverrides: { GLB_EXTRA_DATA: 0 },
    externalResourceFunction: async (uri) => {
      throw new Error("HoloCue validation requires embedded resources: " + uri);
    },
  });
  process.stdout.write(JSON.stringify({ validator_version: validator.version(), report }) + "\n");
}

void main();
