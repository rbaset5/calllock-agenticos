#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const defaultV2Root = "/Users/rashidbaset/conductor/workspaces/retellai-calllock/madrid/V2/src";
const v2Root = process.env.CALLLOCK_V2_ROOT || defaultV2Root;
const packDir = path.join(repoRoot, "knowledge", "industry-packs", "hvac");

function read(relativePath) {
  return fs.readFileSync(path.join(v2Root, relativePath), "utf8");
}

function extractObject(source, variableName) {
  const pattern = new RegExp(`const ${variableName}(?::[^=]+)? = (\\{[\\s\\S]*?\\n\\});`, "m");
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${variableName}`);
  }
  const normalized = match[1].trim().replace(/;$/, "");
  return Function(`"use strict"; return ${normalized};`)();
}

function extractArray(source, variableName) {
  const pattern = new RegExp(`const ${variableName}(?::[^=]+)? = (\\[[\\s\\S]*?\\n\\]);`, "m");
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`Could not find ${variableName}`);
  }
  const normalized = match[1].trim().replace(/;$/, "");
  return Function(`"use strict"; return ${normalized};`)();
}

function writeJsonYaml(filename, value) {
  fs.writeFileSync(path.join(packDir, filename), `${JSON.stringify(value, null, 2)}\n`);
}

const tagsSource = read("classification/tags.ts");
const callTypeSource = read("classification/call-type.ts");
const urgencySource = read("extraction/urgency.ts");
const scorecardSource = read("extraction/call-scorecard.ts");
const prioritySource = read("services/priority-detection.ts");
const revenueSource = read("services/revenue-estimation.ts");
const retellTypes = read("types/retell.ts");
const bookingSource = read("functions/booking.ts");
const calendarSource = read("functions/calendar.ts");
const alertsSource = read("services/alerts.ts");
const postCallSource = read("extraction/post-call.ts");
const hvacIssueSource = read("extraction/hvac-issue.ts");

const categoryVariables = {
  HAZARD: "HAZARD_PATTERNS",
  URGENCY: "URGENCY_PATTERNS",
  SERVICE_TYPE: "SERVICE_TYPE_PATTERNS",
  REVENUE: "REVENUE_PATTERNS",
  RECOVERY: "RECOVERY_PATTERNS",
  LOGISTICS: "LOGISTICS_PATTERNS",
  CUSTOMER: "CUSTOMER_PATTERNS",
  NON_CUSTOMER: "NON_CUSTOMER_PATTERNS",
  CONTEXT: "CONTEXT_PATTERNS",
};

const categories = {};
for (const [category, variableName] of Object.entries(categoryVariables)) {
  const patterns = extractObject(tagsSource, variableName);
  categories[category] = Object.entries(patterns).map(([id, aliases]) => ({ id, aliases }));
}

const smartTagCount = Object.values(categories).reduce((total, tags) => total + tags.length, 0);

const urgencyTiers = {
  source_files: [
    "types/retell.ts",
    "classification/call-type.ts",
    "extraction/urgency.ts",
  ],
  tiers: [
    { id: "LifeSafety", dashboard: "emergency", legacy_level: "Emergency" },
    { id: "Urgent", dashboard: "high", legacy_level: "Urgent" },
    { id: "Routine", dashboard: "medium", legacy_level: "Routine" },
    { id: "Estimate", dashboard: "low", legacy_level: "Estimate" },
  ],
  fallback_patterns: [
    { regex: "gas\\s*leak|carbon\\s*monoxide|smoke|fire|sparking|flood", tier: "LifeSafety" },
    { regex: "water\\s*leak|no\\s*(heat|cool|ac|air)|asap|today|right\\s*away", tier: "Urgent" },
    { regex: "maintenance|tune.?up|this\\s*week", tier: "Routine" },
    { regex: "estimate|quote|how\\s*much|no\\s*rush|flexible", tier: "Estimate" },
  ],
  dashboard_mapping_comment: callTypeSource.includes("all calls showed as 'low' urgency")
    ? "Dashboard mapping must prefer urgencyLevel when urgencyTier is absent."
    : "Dashboard mapping present in V2.",
};

const issueTypes = [...retellTypes.matchAll(/\|\s+"([^"]+)"/g)]
  .map((match) => match[1])
  .filter((value) => [
    "Cooling",
    "Heating",
    "Maintenance",
    "Leaking",
    "No Cool",
    "No Heat",
    "Noisy System",
    "Odor",
    "Not Running",
    "Thermostat",
  ].includes(value));

const serviceTypes = {
  issue_types: issueTypes,
  regex_sources: [
    "water\\s*(leak|puddle|drip|pool)",
    "no\\s*(cold|cool)|warm\\s*air",
    "no\\s*heat|furnace\\s*(not|won)",
    "noise|loud|bang|rattle|squeal|grind",
    "smell|odor|musty|mold",
    "won.t\\s*(start|turn|run)|dead|no\\s*power",
    "thermostat|temperature.*wrong",
    "maintenance|tune.?up|check.?up|seasonal|filter",
  ],
  inferred_from: hvacIssueSource.includes("inferHvacIssueType") ? "inferHvacIssueType()" : "manual",
};

const scoreWeightsMatch = scorecardSource.match(/const WEIGHTS = (\{[\s\S]*?\n\}) as const;/m);
const weights = scoreWeightsMatch ? Function(`"use strict"; return (${scoreWeightsMatch[1]});`)() : {};
const scoring = {
  weights,
  warnings: ["zero-tags", "callback-gap"],
  scale: "0-100",
};

const priorityKeywords = {
  red: extractArray(prioritySource, "RED_KEYWORDS"),
  green: extractArray(prioritySource, "GREEN_KEYWORDS"),
  gray: extractArray(prioritySource, "GRAY_KEYWORDS"),
  default: "blue",
};

const tierConfig = extractObject(revenueSource, "TIER_CONFIG");
const revenueSignals = {
  replacement_refrigerant: extractArray(revenueSource, "REPLACEMENT_REFRIGERANT"),
  replacement_intent: extractArray(revenueSource, "REPLACEMENT_INTENT"),
  major_repair_components: extractArray(revenueSource, "MAJOR_REPAIR_COMPONENTS"),
  major_repair_severity: extractArray(revenueSource, "MAJOR_REPAIR_SEVERITY"),
  standard_repair_components: extractArray(revenueSource, "STANDARD_REPAIR_COMPONENTS"),
  standard_repair_scope: extractArray(revenueSource, "STANDARD_REPAIR_SCOPE"),
  maintenance_service: extractArray(revenueSource, "MAINTENANCE_SERVICE"),
  maintenance_simple: extractArray(revenueSource, "MAINTENANCE_SIMPLE"),
};

const compliance = {
  safety_emergency_regex: "gas\\s*leak|smell\\s*gas|carbon\\s*monoxide|co\\s*detector|smoke\\s*from|electrical\\s*fire|sparking|flooding",
  reply_instructions: alertsSource.match(/const REPLY_INSTRUCTIONS = "([^"]+)"/)?.[1] || "",
  emergency_callback_rule: "Promised callback within {callbackMinutes} min",
  source_files: ["extraction/post-call.ts", "services/alerts.ts"],
};

const booking = {
  provider: "Cal.com",
  event_type_id: bookingSource.match(/CAL_COM_EVENT_TYPE_ID .*? "(\d+)"/)?.[1] || "3877847",
  urgency_routing: {
    Emergency: "within 24 hours",
    Urgent: "within 2 days",
    Routine: "2 to 7 days out",
    Estimate: "2 to 7 days out",
  },
  source_files: ["functions/booking.ts", "functions/calendar.ts"],
};

const reporting = {
  templates: [
    "daily-call-summary",
    "emergency-escalation-report",
    "sales-lead-summary",
  ],
};

const inboundFields = [...retellTypes.matchAll(/^\s{2}([a-zA-Z0-9_?]+):/gm)].map((match) => match[1].replace(/\?$/, ""));
const scriptFrontmatter = (id, title) => `---\nid: ${id}\ntitle: ${title}\ngraph: industry-pack\nowner: platform\nlast_reviewed: 2026-03-12\ntrust_level: curated\nprogressive_disclosure:\n  summary_tokens: 70\n  full_tokens: 140\n---\n\n`;
const inboundScript = `${scriptFrontmatter("hvac-inbound-call-script", "HVAC Inbound Call Script Template")}# Inbound Call Script Template\n\nConversationState fields captured in V2:\n\n${inboundFields.map((field) => `- ${field}`).join("\n")}\n`;
const emergencyDispatch = `${scriptFrontmatter("hvac-emergency-dispatch-script", "HVAC Emergency Dispatch Script")}# Emergency Dispatch\n\nURGENT: {urgencyDescription}\nCaller: {callerPhone}\nAddress: {address}\nPromised callback within {callbackMinutes} min\n${compliance.reply_instructions}\n`;
const bookingConfirmation = `${scriptFrontmatter("hvac-booking-confirmation-script", "HVAC Booking Confirmation Script")}# Booking Confirmation\n\nUse Cal.com event type ${booking.event_type_id}. Confirm the appointment date/time and note that final technician routing remains tenant-config dependent.\n`;

writeJsonYaml("taxonomy.yaml", { categories });
writeJsonYaml("urgency.yaml", urgencyTiers);
writeJsonYaml("service-types.yaml", serviceTypes);
writeJsonYaml("scoring.yaml", scoring);
writeJsonYaml("priority-detection.yaml", priorityKeywords);
writeJsonYaml("revenue-estimation.yaml", { tiers: tierConfig, signals: revenueSignals });
writeJsonYaml("compliance.yaml", compliance);
writeJsonYaml("booking-rules.yaml", booking);
writeJsonYaml("reporting.yaml", reporting);
writeJsonYaml("pack.yaml", {
  pack_id: "hvac",
  version: "0.1.0",
  industry: "HVAC",
  smart_tag_count: smartTagCount,
  migrated_from: "express-v2-hardcoded",
  source_root: v2Root,
  files: [
    "taxonomy.yaml",
    "urgency.yaml",
    "service-types.yaml",
    "scoring.yaml",
    "priority-detection.yaml",
    "revenue-estimation.yaml",
    "compliance.yaml",
    "booking-rules.yaml",
    "reporting.yaml",
    "scripts/inbound-call.md",
    "scripts/emergency-dispatch.md",
    "scripts/booking-confirmation.md",
  ],
});

fs.writeFileSync(path.join(packDir, "scripts", "inbound-call.md"), inboundScript);
fs.writeFileSync(path.join(packDir, "scripts", "emergency-dispatch.md"), emergencyDispatch);
fs.writeFileSync(path.join(packDir, "scripts", "booking-confirmation.md"), bookingConfirmation);

console.log(`Generated HVAC pack with ${smartTagCount} tags from ${v2Root}`);
