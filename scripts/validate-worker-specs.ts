#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const workerDir = path.join(process.cwd(), "knowledge", "worker-specs");
const requiredKeys = [
  "schema_version",
  "worker_id",
  "version",
  "mission",
  "scope",
  "execution_scope",
  "inputs",
  "outputs",
  "tools_allowed",
  "success_metrics",
  "approval_boundaries",
  "dependencies",
];

const files = fs.readdirSync(workerDir).filter((name) => name.endsWith(".yaml"));
const seenIds = new Set();
const errors = [];

for (const file of files) {
  const raw = fs.readFileSync(path.join(workerDir, file), "utf8");
  const spec = JSON.parse(raw);
  for (const key of requiredKeys) {
    if (!(key in spec)) errors.push(`${file} missing ${key}`);
  }
  if (seenIds.has(spec.worker_id)) errors.push(`${file} duplicates worker_id ${spec.worker_id}`);
  seenIds.add(spec.worker_id);
  if (!Array.isArray(spec.tools_allowed) || spec.tools_allowed.some((tool) => typeof tool !== "string" || tool.length === 0)) {
    errors.push(`${file} has invalid tools_allowed`);
  }
  if (!Array.isArray(spec.success_metrics) || spec.success_metrics.length < 2) {
    errors.push(`${file} must define at least 2 success_metrics`);
  } else {
    for (const metric of spec.success_metrics) {
      if (!metric.eval_dataset || typeof metric.eval_dataset !== "string") {
        errors.push(`${file} has success_metric without eval_dataset`);
      }
    }
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Validated ${files.length} worker specs.`);
