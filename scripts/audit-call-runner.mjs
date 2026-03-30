#!/usr/bin/env node
/**
 * audit-call-runner.mjs — Fetch all data needed for a /audit-call report
 *
 * Usage:
 *   node scripts/audit-call-runner.mjs last
 *   node scripts/audit-call-runner.mjs call_abc123          (Retell call ID)
 *   node scripts/audit-call-runner.mjs +13125551234         (phone number)
 *   node scripts/audit-call-runner.mjs <uuid>               (call_records.id)
 *
 * Reads env vars from web/.env.local if present.
 * Outputs structured JSON to stdout for consumption by /audit-call skill.
 */

import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");

// --- Load .env.local ---
function loadEnv(filePath) {
  if (!existsSync(filePath)) return;
  const lines = readFileSync(filePath, "utf-8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    let value = trimmed.slice(eqIdx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

loadEnv(resolve(REPO_ROOT, "web/.env.local"));
loadEnv(resolve(REPO_ROOT, ".env.local"));

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const RETELL_API_KEY = process.env.RETELL_API_KEY;

// The actual table used by the voice pipeline (migration 048)
const CALLS_TABLE = "call_records";

// Columns in the call_records table (migration 048_voice_config.sql)
const CALLS_SELECT = [
  "id", "tenant_id", "call_id", "retell_call_id", "phone_number",
  "transcript", "extracted_fields", "extraction_status",
  "quality_score", "tags", "route",
  "urgency_tier", "caller_type", "primary_intent", "revenue_tier",
  "booking_id", "callback_scheduled",
  "call_duration_seconds", "end_call_reason", "call_recording_url",
  "synced_to_app",
  "created_at", "updated_at",
].join(",");

// --- Supabase helpers ---
async function supabaseGet(table, params = {}) {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  }
  const url = new URL(`${SUPABASE_URL.replace(/\/$/, "")}/rest/v1/${table}`);
  for (const [k, v] of Object.entries(params)) {
    url.searchParams.set(k, v);
  }
  const res = await fetch(url.toString(), {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
    },
  });
  if (!res.ok) {
    throw new Error(`Supabase ${table}: HTTP ${res.status} — ${await res.text()}`);
  }
  return res.json();
}

// --- Retell helpers ---
async function retellGetCall(callId) {
  if (!RETELL_API_KEY) return null;
  const res = await fetch(`https://api.retellai.com/v2/get-call/${callId}`, {
    headers: { Authorization: `Bearer ${RETELL_API_KEY}` },
  });
  if (!res.ok) return null;
  return res.json();
}

// --- Resolve identifier to a call record ---
async function resolveCall(identifier) {
  if (identifier === "last") {
    const rows = await supabaseGet(CALLS_TABLE, {
      select: CALLS_SELECT,
      order: "created_at.desc",
      limit: "1",
    });
    return rows[0] || null;
  }

  // Phone number (starts with +)
  if (identifier.startsWith("+")) {
    const rows = await supabaseGet(CALLS_TABLE, {
      select: CALLS_SELECT,
      phone_number: `eq.${identifier}`,
      order: "created_at.desc",
      limit: "1",
    });
    return rows[0] || null;
  }

  // UUID format — try call_records.id
  const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (uuidRe.test(identifier)) {
    const rows = await supabaseGet(CALLS_TABLE, {
      select: CALLS_SELECT,
      id: `eq.${identifier}`,
      limit: "1",
    });
    if (rows.length) return rows[0];
  }

  // Retell call ID (call_xxx format) — try retell_call_id, then call_id
  for (const col of ["retell_call_id", "call_id"]) {
    const rows = await supabaseGet(CALLS_TABLE, {
      select: CALLS_SELECT,
      [col]: `eq.${identifier}`,
      limit: "1",
    });
    if (rows.length) return rows[0];
  }

  return null;
}

// --- Parse state flow from Retell transcript ---
function parseStateFlow(retellData) {
  if (!retellData || !retellData.transcript_object) return null;

  const entries = retellData.transcript_object;
  if (!Array.isArray(entries)) return null;

  const stateSequence = [];
  const toolCalls = [];
  const toolResults = [];
  let transitionSource = "unknown";

  for (const entry of entries) {
    const role = entry.role || "";
    const content = entry.content || "";
    const name = entry.name || "";

    if (role === "node_transition") {
      stateSequence.push(content || name);
      transitionSource = "node_transition";
      continue;
    }

    if (role === "tool_call_invocation") {
      if (name.startsWith("transition_to_")) {
        stateSequence.push(name.replace("transition_to_", ""));
        transitionSource = "tool_call_invocation";
      } else {
        toolCalls.push({ name, args: entry.arguments || content });
      }
      continue;
    }

    if (role === "tool_call_result") {
      toolResults.push({ name, result: content });
      continue;
    }
  }

  const terminalState =
    retellData.call_analysis?.custom_analysis_data?.last_node_name ||
    retellData.call_analysis?.custom_analysis_data?.current_agent_state ||
    (stateSequence.length ? stateSequence[stateSequence.length - 1] : "unknown");

  return {
    state_sequence: stateSequence,
    transition_source: transitionSource,
    tool_calls: toolCalls,
    tool_results: toolResults,
    terminal_state: terminalState,
  };
}

// --- Main ---
async function main() {
  const identifier = process.argv[2];
  if (!identifier) {
    console.error("Usage: node scripts/audit-call-runner.mjs <last | call_id | phone | uuid>");
    process.exit(1);
  }

  const errors = [];
  const output = { call: null, retell: null, state_flow: null, errors };

  // Step 1: Resolve call from Supabase call_records table
  try {
    output.call = await resolveCall(identifier);
  } catch (e) {
    errors.push({ step: "supabase_query", message: e.message });
  }

  if (!output.call) {
    errors.push({ step: "resolve", message: `No call found for identifier: ${identifier}` });
    console.log(JSON.stringify(output, null, 2));
    process.exit(1);
  }

  // Step 2: Fetch Retell data
  const retellId = output.call.retell_call_id || output.call.call_id;
  if (retellId && RETELL_API_KEY) {
    try {
      const retellData = await retellGetCall(retellId);
      if (retellData) {
        output.retell = {
          call_id: retellData.call_id,
          call_status: retellData.call_status,
          start_timestamp: retellData.start_timestamp,
          end_timestamp: retellData.end_timestamp,
          duration_ms: retellData.duration_ms,
          disconnection_reason: retellData.disconnection_reason,
          call_analysis: retellData.call_analysis || null,
          collected_dynamic_variables: retellData.retell_llm_dynamic_variables || null,
          transcript_entry_count: Array.isArray(retellData.transcript_object)
            ? retellData.transcript_object.length
            : 0,
        };

        // Step 3: Parse state flow
        output.state_flow = parseStateFlow(retellData);
      }
    } catch (e) {
      errors.push({ step: "retell_api", message: e.message });
    }
  } else if (!RETELL_API_KEY) {
    errors.push({ step: "retell_api", message: "RETELL_API_KEY not set — skipping Retell data" });
  }

  // Truncate transcript for readability (keep extracted_fields intact)
  if (output.call.transcript && output.call.transcript.length > 3000) {
    output.call.transcript_length = output.call.transcript.length;
    output.call.transcript = output.call.transcript.slice(0, 500) + "\n...[truncated]...";
  }

  console.log(JSON.stringify(output, null, 2));
}

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
