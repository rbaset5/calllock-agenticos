#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const packDir = path.join(process.cwd(), "knowledge", "industry-packs", "hvac");

function loadYaml(filePath: string): any {
  const json = execFileSync(
    "python3",
    ["-c", "import yaml,json,sys; docs=list(yaml.safe_load_all(sys.stdin)); print(json.dumps(docs[-1] if len(docs)>1 else docs[0]))"],
    { input: fs.readFileSync(filePath, "utf8"), encoding: "utf8" },
  );
  return JSON.parse(json);
}

function loadJson(filePath: string): any {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

const manifest = loadJson(path.join(packDir, "pack.yaml"));
const taxonomy = loadYaml(path.join(packDir, "taxonomy.yaml"));
const urgency = loadJson(path.join(packDir, "urgency.yaml"));

const errors: string[] = [];

for (const required of ["pack_id", "version", "industry", "smart_tag_count", "files"]) {
  if (!(required in manifest)) errors.push(`pack.yaml missing ${required}`);
}

for (const file of manifest.files || []) {
  if (!fs.existsSync(path.join(packDir, file))) {
    errors.push(`pack.yaml references missing file ${file}`);
  }
}

const actualTagCount = Object.values(taxonomy.categories || {}).reduce(
  (total: number, tags: any) => total + (tags as any[]).length,
  0,
);
if (manifest.smart_tag_count !== actualTagCount) {
  errors.push(`smart_tag_count mismatch: manifest=${manifest.smart_tag_count} actual=${actualTagCount}`);
}

if (!Array.isArray(urgency.tiers) || urgency.tiers.length !== 4) {
  errors.push("urgency.yaml must define 4 tiers");
}

for (const [category, tags] of Object.entries(taxonomy.categories || {})) {
  for (const tag of tags as any[]) {
    if (!tag.name || !Array.isArray(tag.patterns)) {
      errors.push(`taxonomy category ${category} has invalid tag entry (missing name or patterns)`);
    }
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Validated HVAC pack with ${actualTagCount} tags.`);
