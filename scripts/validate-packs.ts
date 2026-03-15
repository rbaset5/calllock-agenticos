#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const packDir = path.join(process.cwd(), "knowledge", "industry-packs", "hvac");
const manifest = JSON.parse(fs.readFileSync(path.join(packDir, "pack.yaml"), "utf8"));
const taxonomy = JSON.parse(fs.readFileSync(path.join(packDir, "taxonomy.yaml"), "utf8"));
const urgency = JSON.parse(fs.readFileSync(path.join(packDir, "urgency.yaml"), "utf8"));

const errors = [];

for (const required of ["pack_id", "version", "industry", "smart_tag_count", "files"]) {
  if (!(required in manifest)) errors.push(`pack.yaml missing ${required}`);
}

for (const file of manifest.files || []) {
  if (!fs.existsSync(path.join(packDir, file))) {
    errors.push(`pack.yaml references missing file ${file}`);
  }
}

const actualTagCount = Object.values(taxonomy.categories || {}).reduce(
  (total, tags) => total + tags.length,
  0,
);
if (manifest.smart_tag_count !== actualTagCount) {
  errors.push(`smart_tag_count mismatch: manifest=${manifest.smart_tag_count} actual=${actualTagCount}`);
}

if (!Array.isArray(urgency.tiers) || urgency.tiers.length !== 4) {
  errors.push("urgency.yaml must define 4 tiers");
}

for (const [category, tags] of Object.entries(taxonomy.categories || {})) {
  for (const tag of tags) {
    if (!tag.id || !Array.isArray(tag.aliases)) {
      errors.push(`taxonomy category ${category} has invalid tag entry`);
    }
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Validated HVAC pack with ${actualTagCount} tags.`);
