#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const knowledgeRoot = path.join(root, "knowledge");
const todayIso = new Date().toISOString().slice(0, 10);
const requiredFrontmatter = [
  "id",
  "title",
  "graph",
  "owner",
  "last_reviewed",
  "trust_level",
  "progressive_disclosure.summary_tokens",
  "progressive_disclosure.full_tokens",
];

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const target = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(target);
    return [target];
  });
}

function parseFrontmatter(content) {
  if (!content.startsWith("---\n")) return [{}, content];
  const parts = content.split("\n---\n");
  const raw = parts[0].replace(/^---\n/, "");
  const metadata = {};
  let parent = "";
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    if (line.startsWith("  ") && parent) {
      const [key, ...rest] = line.trim().split(":");
      metadata[`${parent}.${key.trim()}`] = rest.join(":").trim();
      continue;
    }
    const [key, ...rest] = line.split(":");
    metadata[key.trim()] = rest.join(":").trim();
    parent = metadata[key.trim()] ? "" : key.trim();
  }
  return [metadata, parts.slice(1).join("\n---\n")];
}

function wikiLinks(content) {
  return [...content.matchAll(/\[\[([^\]]+)\]\]/g)].map((match) => match[1]);
}

const markdownFiles = walk(knowledgeRoot).filter((file) => file.endsWith(".md"));
const errors = [];

for (const file of markdownFiles) {
  const content = fs.readFileSync(file, "utf8");
  const [metadata, body] = parseFrontmatter(content);
  for (const key of requiredFrontmatter) {
    if (!(key in metadata)) {
      errors.push(`${path.relative(root, file)} missing frontmatter key ${key}`);
    }
  }
  if (metadata.last_reviewed) {
    const reviewedAt = new Date(metadata.last_reviewed);
    if (Number.isNaN(reviewedAt.getTime())) {
      errors.push(`${path.relative(root, file)} has an invalid last_reviewed date`);
    } else if (metadata.last_reviewed > todayIso) {
      errors.push(`${path.relative(root, file)} has a future last_reviewed date`);
    }
  }
  for (const link of wikiLinks(body)) {
    const target = path.join(knowledgeRoot, `${link}.md`);
    if (!fs.existsSync(target)) {
      errors.push(`${path.relative(root, file)} contains unresolved wiki link [[${link}]]`);
    }
  }
}

const directories = new Set(markdownFiles.map((file) => path.dirname(file)));
for (const dir of directories) {
  const children = fs.readdirSync(dir).filter((name) => name.endsWith(".md") && name !== "_moc.md");
  if (children.length === 0) continue;
  const mocPath = path.join(dir, "_moc.md");
  if (!fs.existsSync(mocPath)) {
    errors.push(`${path.relative(root, dir)} missing _moc.md`);
    continue;
  }
  const mocContent = fs.readFileSync(mocPath, "utf8");
  for (const child of children) {
    const basename = child.replace(/\.md$/, "");
    if (!mocContent.includes(`[[${path.relative(knowledgeRoot, path.join(dir, basename)).replace(/\\/g, "/")}]]`) && !mocContent.includes(child)) {
      errors.push(`${path.relative(root, mocPath)} does not reference ${child}`);
    }
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Validated ${markdownFiles.length} knowledge markdown files.`);
