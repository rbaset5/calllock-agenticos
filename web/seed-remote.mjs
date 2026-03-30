#!/usr/bin/env node
/**
 * seed-remote.mjs — Run the demo seed against the remote Supabase project.
 *
 * Usage:
 *   node supabase/seed-remote.mjs
 *
 * Reads NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env.local
 * (project root) or environment. The service role key bypasses RLS.
 *
 * What it does:
 *  1. Deletes all demo-call-* records for tenant-alpha (cascades to callback_touches)
 *  2. Inserts 28 call_records
 *  3. Deletes trigger-inserted callback_touches for demo-call-*
 *  4. Inserts 10 callback_touches with precise relative timestamps
 */

import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

// ── Env loading ────────────────────────────────────────────────────────────────
const __dir = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dir, "../.env.local");

function loadEnv(filePath) {
  try {
    const lines = readFileSync(filePath, "utf8").split("\n");
    for (const line of lines) {
      const m = line.match(/^([^=]+)=(.*)$/);
      if (m && !process.env[m[1].trim()]) {
        process.env[m[1].trim()] = m[2].trim().replace(/^["']|["']$/g, "");
      }
    }
  } catch {}
}
loadEnv(envPath);

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false },
});

const TENANT_ALPHA = "00000000-0000-0000-0000-000000000001";

// ── Time helpers ──────────────────────────────────────────────────────────────
const now = new Date();
const ago = (ms) => new Date(now.getTime() - ms).toISOString();
const future = (ms) => new Date(now.getTime() + ms).toISOString();

const MIN = 60 * 1000;
const HR = 60 * MIN;
const DAY = 24 * HR;

// ── Step 1: Delete old demo-call records (cascades to callback_touches) ────────
console.log("Step 1: Deleting old demo-call-* records…");
const { error: delErr } = await supabase
  .from("call_records")
  .delete()
  .eq("tenant_id", TENANT_ALPHA)
  .like("call_id", "demo-call-%");
if (delErr) { console.error("Delete failed:", delErr); process.exit(1); }
console.log("  ✓ Deleted");

// ── Step 2: Insert 28 call_records ───────────────────────────────────────────
console.log("Step 2: Inserting 28 call_records…");

function record({
  callId, retellCallId, phone, transcript, fields, extractionStatus,
  urgencyTier, endCallReason, callbackScheduled, callbackOutcome, callbackOutcomeAt,
  callerType, primaryIntent, revenueTier, route, recordingUrl, qualityScore,
  tags, durationSeconds, bookingStatus, bookingStatusAt, bookingNotes,
  createdAt, updatedAt,
}) {
  return {
    tenant_id: TENANT_ALPHA,
    call_id: callId,
    retell_call_id: retellCallId,
    phone_number: phone,
    transcript,
    extracted_fields: fields,
    extraction_status: extractionStatus,
    urgency_tier: urgencyTier,
    end_call_reason: endCallReason,
    callback_scheduled: callbackScheduled ?? false,
    callback_outcome: callbackOutcome ?? null,
    callback_outcome_at: callbackOutcomeAt ?? null,
    caller_type: callerType ?? null,
    primary_intent: primaryIntent ?? null,
    revenue_tier: revenueTier ?? null,
    route: route ?? null,
    call_recording_url: recordingUrl ?? null,
    quality_score: qualityScore ?? null,
    tags: tags ?? [],
    call_duration_seconds: durationSeconds ?? null,
    booking_status: bookingStatus ?? null,
    booking_status_at: bookingStatusAt ?? null,
    booking_notes: bookingNotes ?? null,
    raw_retell_payload: {},
    created_at: createdAt,
    updated_at: updatedAt,
  };
}

function fields(f) { return f; }

const records = [
  // ── ESCALATED_BY_AI (3) ────────────────────────────────────────────────────
  record({
    callId: "demo-call-001", retellCallId: "retell-demo-001", phone: "+13135550001",
    transcript: "Agent: Metro HVAC, how can I help?\nUser: There's a strong gas smell in my house. My family is outside.\nAgent: Life-safety emergency. Stay outside, call 911. Dispatching tech.",
    fields: fields({ customer_name: "Marcus Neal", customer_phone: "+13135550001", service_address: "1842 Woodward Ave, Detroit, MI 48201", problem_description: "Strong gas smell; family evacuated. Furnace suspected.", hvac_issue_type: "Odor", is_safety_emergency: true, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Lennox", equipment_age: "12 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "LifeSafety", endCallReason: "safety_emergency",
    callerType: "residential", primaryIntent: "service", revenueTier: "major_repair", route: "legitimate",
    recordingUrl: "https://example.com/recordings/demo-call-001.mp3",
    qualityScore: 9.4, tags: ["escalated","safety","gas-leak"], durationSeconds: 94,
    createdAt: ago(14 * MIN), updatedAt: ago(14 * MIN),
  }),
  record({
    callId: "demo-call-002", retellCallId: "retell-demo-002", phone: "+13135550002",
    transcript: "Agent: Metro HVAC.\nUser: My AC has been out since yesterday. My 84-year-old father is home alone and it's 94 degrees out.\nAgent: This is urgent. Escalating to our team right now.",
    fields: fields({ customer_name: "Dana Kowalski", customer_phone: "+13135550002", service_address: "3120 Gratiot Ave, Detroit, MI 48207", problem_description: "No cooling for 24h. Elderly parent home alone during heat advisory.", hvac_issue_type: "No Cool", is_safety_emergency: false, is_urgent_escalation: true, equipment_type: "Central AC", equipment_brand: "Carrier", equipment_age: "15 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "LifeSafety", endCallReason: "urgent_escalation",
    callerType: "residential", primaryIntent: "service", revenueTier: "major_repair", route: "legitimate",
    recordingUrl: "https://example.com/recordings/demo-call-002.mp3",
    qualityScore: 9.1, tags: ["escalated","urgent","no-cool","vulnerable"], durationSeconds: 118,
    createdAt: ago(55 * MIN), updatedAt: ago(55 * MIN),
  }),
  record({
    callId: "demo-call-003", retellCallId: "retell-demo-003", phone: "+13135550003",
    transcript: "Agent: Metro HVAC.\nUser: Our CO detector went off in the basement. We think it's the furnace. We're outside now.\nAgent: Stay outside. Carbon monoxide emergency. Call 911. Alerting dispatch.",
    fields: fields({ customer_name: "James Whitfield", customer_phone: "+13135550003", service_address: "5902 Livernois Ave, Detroit, MI 48210", problem_description: "CO detector triggered. Family outside. Furnace suspected source.", hvac_issue_type: "Odor", is_safety_emergency: true, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Rheem", equipment_age: "8 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "LifeSafety", endCallReason: "safety_emergency",
    callerType: "residential", primaryIntent: "service", revenueTier: "major_repair", route: "legitimate",
    recordingUrl: "https://example.com/recordings/demo-call-003.mp3",
    qualityScore: 9.6, tags: ["escalated","safety","co-alarm"], durationSeconds: 82,
    createdAt: ago(8 * MIN), updatedAt: ago(8 * MIN),
  }),

  // ── NEW_LEADS (9) ──────────────────────────────────────────────────────────
  record({
    callId: "demo-call-004", retellCallId: "retell-demo-004", phone: "+13135550004",
    transcript: "Agent: Metro HVAC, how can I help?\nUser: My AC is blowing warm air and the house is already at 88 degrees.\nAgent: Flagging as urgent. Calling you back shortly.",
    fields: fields({ customer_name: "Ariana Holt", customer_phone: "+13135550004", service_address: "2154 Cass Ave, Detroit, MI 48201", problem_description: "AC blowing warm air; indoor temp 88F.", hvac_issue_type: "No Cool", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Carrier", equipment_age: "9 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Urgent", endCallReason: "customer_hangup",
    callerType: "residential", primaryIntent: "service", revenueTier: "major_repair", route: "legitimate",
    recordingUrl: "https://example.com/recordings/demo-call-004.mp3",
    qualityScore: 8.9, tags: ["new-lead","urgent","no-cool"], durationSeconds: 178,
    createdAt: ago(18 * MIN), updatedAt: ago(18 * MIN),
  }),
  record({
    callId: "demo-call-005", retellCallId: "retell-demo-005", phone: "+13135550005",
    transcript: "Agent: Metro HVAC.\nUser: Water is dripping from my attic air handler. There's a small puddle on the floor.\nAgent: Sounds like a condensate drain clog. Getting a tech out today.",
    fields: fields({ customer_name: "Miguel Price", customer_phone: "+13135550005", service_address: "4701 Grand River Ave, Detroit, MI 48208", problem_description: "Water dripping from attic air handler. Puddle forming.", hvac_issue_type: "Leaking", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Air Handler", equipment_brand: "Trane", equipment_age: "6 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: "residential", primaryIntent: "service", revenueTier: "standard_repair", route: "legitimate",
    qualityScore: 8.2, tags: ["new-lead","leak"], durationSeconds: 152,
    createdAt: ago(35 * MIN), updatedAt: ago(35 * MIN),
  }),
  record({
    callId: "demo-call-006", retellCallId: "retell-demo-006", phone: "+13135550006",
    transcript: "Agent: Metro HVAC.\nUser: I want a replacement estimate for our 20-year-old system. It runs but barely cools.\nAgent: Having our comfort advisor call you today.",
    fields: fields({ customer_name: "Claire Benton", customer_phone: "+13135550006", service_address: "7830 Michigan Ave, Detroit, MI 48210", problem_description: "Requesting replacement estimate. 20-year-old system barely cooling.", hvac_issue_type: "Cooling", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC + Furnace", equipment_brand: "York", equipment_age: "20 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Estimate", endCallReason: "customer_hangup",
    callerType: "residential", primaryIntent: "estimate", revenueTier: "replacement", route: "legitimate",
    qualityScore: 7.8, tags: ["new-lead","estimate","replacement"], durationSeconds: 201,
    createdAt: ago(70 * MIN), updatedAt: ago(70 * MIN),
  }),
  record({
    callId: "demo-call-007", retellCallId: "retell-demo-007", phone: "+13135550007",
    transcript: "Agent: Metro HVAC.\nUser: Just looking into maintenance plans. No current issue, just planning ahead.\nAgent: Great. Someone will reach out with plan options.",
    fields: fields({ customer_name: "Darnell Jones", customer_phone: "+13135550007", service_address: "910 E Jefferson Ave, Detroit, MI 48207", problem_description: "Browsing maintenance plan options. No active issue.", hvac_issue_type: "Maintenance", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central HVAC", equipment_brand: "Lennox", equipment_age: "4 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: "residential", primaryIntent: "maintenance", revenueTier: "minor", route: "legitimate",
    qualityScore: 7.4, tags: ["new-lead","maintenance","low-priority"], durationSeconds: 134,
    createdAt: ago(2 * HR), updatedAt: ago(2 * HR),
  }),
  record({
    callId: "demo-call-008", retellCallId: "retell-demo-008", phone: "+13135550008",
    transcript: "Agent: Metro HVAC.\nUser: Can you add me to the waitlist for the next available tech for an AC check?\nAgent: You're on the waitlist. We'll call when a slot opens up.",
    fields: fields({ customer_name: "Lena Patel", customer_phone: "+13135550008", service_address: "1506 W Grand Blvd, Detroit, MI 48208", problem_description: "Requested waitlist for next available tech. AC check needed.", hvac_issue_type: "Cooling", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Goodman", equipment_age: "5 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "waitlist_added",
    callerType: "residential", primaryIntent: "service", revenueTier: "diagnostic", route: "legitimate",
    qualityScore: 7.6, tags: ["new-lead","waitlist"], durationSeconds: 112,
    createdAt: ago(160 * MIN), updatedAt: ago(160 * MIN),
  }),
  record({
    callId: "demo-call-009", retellCallId: "retell-demo-009", phone: "+13135550009",
    transcript: "Agent: Metro HVAC.\nUser: I manage a 12-unit apartment complex on East Jefferson. Looking for a maintenance contract.\nAgent: Our commercial team will call you to put together a proposal.",
    fields: fields({ customer_name: "Asha Reynolds", customer_phone: "+13135550009", service_address: "2900 E Jefferson Ave, Detroit, MI 48207", problem_description: "Seeking annual maintenance contract for 12-unit complex.", hvac_issue_type: "Maintenance", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Multiple Units", equipment_brand: "Mixed", equipment_age: "Various", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "sales_lead",
    callerType: "property_manager", primaryIntent: "estimate", revenueTier: "replacement", route: "legitimate",
    qualityScore: 8.5, tags: ["new-lead","commercial","contract"], durationSeconds: 187,
    createdAt: ago(195 * MIN), updatedAt: ago(195 * MIN),
  }),
  record({
    callId: "demo-call-010", retellCallId: "retell-demo-010", phone: "+13135550010",
    transcript: "Agent: Metro HVAC.\nUser: Hi, I called earlier about my AC. Just checking if someone is going to call me back.\nAgent: I see your record. Making sure someone follows up shortly.",
    fields: fields({ customer_name: "Noah Spencer", customer_phone: "+13135550010", service_address: null, problem_description: "Reconnect call — checking on callback status from earlier call.", hvac_issue_type: null, is_safety_emergency: false, is_urgent_escalation: false, equipment_type: null, equipment_brand: null, equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "pending", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: null, primaryIntent: null, revenueTier: null, route: null,
    tags: ["new-lead","pending-extraction"], durationSeconds: 67,
    createdAt: ago(25 * MIN), updatedAt: ago(25 * MIN),
  }),
  record({
    callId: "demo-call-011", retellCallId: "retell-demo-011", phone: "+13135550011",
    transcript: "Agent: Metro HVAC.\nUser: My heat went out last night. It's really cold in here. I have a baby at home.\nAgent: This is urgent. Someone will call you back within 15 minutes.",
    fields: fields({ customer_name: "Jamal Carter", customer_phone: "+13135550011", service_address: "8341 Dexter Ave, Detroit, MI 48206", problem_description: "No heat overnight. Infant at home. Cold indoor temp.", hvac_issue_type: "No Heat", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: null, equipment_brand: null, equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "pending", urgencyTier: "Urgent", endCallReason: "customer_hangup",
    callerType: null, primaryIntent: null, revenueTier: null, route: null,
    tags: ["new-lead","pending-extraction","no-heat","urgent"], durationSeconds: 103,
    createdAt: ago(42 * MIN), updatedAt: ago(42 * MIN),
  }),
  record({
    callId: "demo-call-012", retellCallId: "retell-demo-012", phone: "+13135550012",
    transcript: "Agent: Metro HVAC.\nUser: My outdoor AC unit started making a loud rattling noise yesterday. Still running but sounds terrible.\nAgent: Could be a loose part or debris. Sending someone to look.",
    fields: fields({ customer_name: "Tamika Washington", customer_phone: "+13135550012", service_address: "6120 Schaefer Rd, Dearborn, MI 48126", problem_description: "Loud rattling noise from outdoor AC unit. Still running.", hvac_issue_type: "Noisy System", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Goodman", equipment_age: "7 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: "residential", primaryIntent: "service", revenueTier: "diagnostic", route: "legitimate",
    qualityScore: 8.1, tags: ["new-lead","noisy-system"], durationSeconds: 156,
    createdAt: ago(110 * MIN), updatedAt: ago(110 * MIN),
  }),

  // ── FOLLOW_UPS (6) ─────────────────────────────────────────────────────────
  record({
    callId: "demo-call-013", retellCallId: "retell-demo-013", phone: "+13135550013",
    transcript: "Agent: Metro HVAC.\nUser: I tried booking online but it kept failing. Really need someone out this week.\nAgent: Sorry about that. We'll call back to confirm booking.",
    fields: fields({ customer_name: "Kevin Turner", customer_phone: "+13135550013", service_address: "3201 Rosa Parks Blvd, Detroit, MI 48208", problem_description: "Booking failed during online attempt. Needs tech this week.", hvac_issue_type: "Cooling", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Carrier", equipment_age: "11 years", appointment_booked: false, appointment_datetime: null, callback_type: "preferred", callback_window_start: null, callback_window_end: ago(-1 * HR) }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "booking_failed",
    callbackOutcome: "no_answer", callbackOutcomeAt: ago(7 * HR),
    callerType: "residential", primaryIntent: "service", revenueTier: "standard_repair", route: "legitimate",
    qualityScore: 7.9, tags: ["follow-up","booking-failed"], durationSeconds: 143,
    createdAt: ago(200 * MIN), updatedAt: ago(7 * HR),
  }),
  record({
    callId: "demo-call-014", retellCallId: "retell-demo-014", phone: "+13135550014",
    transcript: "Agent: Metro HVAC.\nUser: A tech came out two days ago and my heat is still not working. This is unacceptable.\nAgent: I sincerely apologize. Escalating to our service manager immediately.",
    fields: fields({ customer_name: "Sonia Gupta", customer_phone: "+13135550014", service_address: "4890 Woodward Ave, Detroit, MI 48201", problem_description: "Tech visited 2 days ago. Heat still not working. Formal complaint.", hvac_issue_type: "No Heat", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Trane", equipment_age: "3 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Urgent", endCallReason: "customer_hangup",
    callbackOutcome: "no_answer", callbackOutcomeAt: ago(11 * HR),
    callerType: "residential", primaryIntent: "complaint", revenueTier: "standard_repair", route: "legitimate",
    qualityScore: 6.8, tags: ["follow-up","complaint","no-heat"], durationSeconds: 167,
    createdAt: ago(6 * HR), updatedAt: ago(11 * HR),
  }),
  record({
    callId: "demo-call-015", retellCallId: "retell-demo-015", phone: "+13135550015",
    transcript: "Agent: Metro HVAC.\nUser: Your tech is at my house right now but he says he doesn't have the right part.\nAgent: I understand your frustration. Connecting you with dispatch.",
    fields: fields({ customer_name: "Trevor Bell", customer_phone: "+13135550015", service_address: "7644 Livernois Ave, Detroit, MI 48210", problem_description: "Active job — tech on site lacks required part. Customer frustrated.", hvac_issue_type: "Heating", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Rheem", equipment_age: "6 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Urgent", endCallReason: "customer_hangup",
    callbackOutcome: "no_answer", callbackOutcomeAt: ago(4 * HR),
    callerType: "residential", primaryIntent: "active_job_issue", revenueTier: "standard_repair", route: "legitimate",
    qualityScore: 7.2, tags: ["follow-up","active-job","parts"], durationSeconds: 189,
    createdAt: ago(9 * HR), updatedAt: ago(4 * HR),
  }),
  record({
    callId: "demo-call-016", retellCallId: "retell-demo-016", phone: "+13135550016",
    transcript: "Agent: Metro HVAC.\nUser: I'd prefer to be called back between 2 and 4 PM today. It's about my thermostat acting up.\nAgent: Noted. Scheduling callback for that window.",
    fields: fields({ customer_name: "Priya Mathur", customer_phone: "+13135550016", service_address: "2240 West Grand Blvd, Detroit, MI 48208", problem_description: "Thermostat acting erratically. Requested callback 2–4 PM today.", hvac_issue_type: "Thermostat", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Smart Thermostat", equipment_brand: "Ecobee", equipment_age: "2 years", appointment_booked: false, appointment_datetime: null, callback_type: "requested", callback_window_start: future(30 * MIN), callback_window_end: future(150 * MIN) }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "callback_later",
    callbackScheduled: true, callbackOutcome: "left_voicemail", callbackOutcomeAt: ago(6 * HR),
    callerType: "residential", primaryIntent: "service", revenueTier: "minor", route: "legitimate",
    qualityScore: 8.3, tags: ["follow-up","callback-requested","thermostat"], durationSeconds: 121,
    createdAt: ago(85 * MIN), updatedAt: ago(6 * HR),
  }),
  record({
    callId: "demo-call-017", retellCallId: "retell-demo-017", phone: "+13135550017",
    transcript: "Agent: Metro HVAC.\nUser: I was trying to get a quote on a mini-split installation. Left a message before.\nAgent: Making sure someone calls you back today with pricing.",
    fields: fields({ customer_name: "Monica Reed", customer_phone: "+13135550017", service_address: "5510 Kercheval Ave, Grosse Pointe, MI 48224", problem_description: "Quote requested for mini-split installation. Second contact attempt.", hvac_issue_type: "Cooling", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Mini-Split", equipment_brand: "Mitsubishi", equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Estimate", endCallReason: "customer_hangup",
    callbackOutcome: "left_voicemail", callbackOutcomeAt: ago(9 * HR),
    callerType: "residential", primaryIntent: "estimate", revenueTier: "replacement", route: "legitimate",
    qualityScore: 7.5, tags: ["follow-up","no-answer","estimate"], durationSeconds: 98,
    createdAt: ago(10 * HR), updatedAt: ago(9 * HR),
  }),
  record({
    callId: "demo-call-018", retellCallId: "retell-demo-018", phone: "+13135550018",
    transcript: "Agent: Metro HVAC.\nUser: I got the diagnostic done last week. The tech said to follow up about whether I want to proceed with the repair.\nAgent: Passing that along. Someone will call you to discuss options.",
    fields: fields({ customer_name: "Hector Flores", customer_phone: "+13135550018", service_address: "1388 Dix Ave, Lincoln Park, MI 48146", problem_description: "Post-diagnostic follow-up. Deciding whether to proceed with repair.", hvac_issue_type: "No Cool", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Carrier", equipment_age: "14 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callbackOutcome: "left_voicemail", callbackOutcomeAt: ago(10 * HR),
    callerType: "residential", primaryIntent: "followup", revenueTier: "diagnostic", route: "legitimate",
    qualityScore: 8.0, tags: ["follow-up","post-diagnostic"], durationSeconds: 145,
    createdAt: ago(5 * HR), updatedAt: ago(10 * HR),
  }),

  // ── BOOKINGS (4 visible + 1 cancelled → OTHER) ─────────────────────────────
  record({
    callId: "demo-call-019", retellCallId: "retell-demo-019", phone: "+13135550019",
    transcript: "Agent: Metro HVAC.\nUser: I'd like to book an AC tune-up. Tomorrow afternoon works best for me.\nAgent: Booked for AC tune-up tomorrow at 2 PM.",
    fields: fields({ customer_name: "Priya Sharma", customer_phone: "+13135550019", service_address: "3904 Vernor Hwy, Detroit, MI 48209", problem_description: "Annual AC tune-up requested. System running fine.", hvac_issue_type: "Maintenance", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Lennox", equipment_age: "5 years", appointment_booked: true, appointment_datetime: future(26 * HR), callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "completed",
    callerType: "residential", primaryIntent: "maintenance", revenueTier: "minor", route: "legitimate",
    qualityScore: 8.7, tags: ["booking","unconfirmed","tune-up"], durationSeconds: 167,
    createdAt: ago(3 * HR), updatedAt: ago(3 * HR),
  }),
  record({
    callId: "demo-call-020", retellCallId: "retell-demo-020", phone: "+13135550020",
    transcript: "Agent: Metro HVAC.\nUser: I need a furnace inspection before the heating season. Can I get something in the next few days?\nAgent: Booked for furnace inspection in two days.\nUser: Morning is perfect.",
    fields: fields({ customer_name: "Marcus Webb", customer_phone: "+13135550020", service_address: "8720 Wyoming Ave, Detroit, MI 48204", problem_description: "Pre-season furnace inspection. No current issue.", hvac_issue_type: "Heating", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Goodman", equipment_age: "9 years", appointment_booked: true, appointment_datetime: future(50 * HR), callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "completed",
    callerType: "residential", primaryIntent: "maintenance", revenueTier: "diagnostic", route: "legitimate",
    qualityScore: 8.4, tags: ["booking","unconfirmed","furnace-inspection"], durationSeconds: 192,
    createdAt: ago(5 * HR), updatedAt: ago(5 * HR),
  }),
  record({
    callId: "demo-call-021", retellCallId: "retell-demo-021", phone: "+13135550021",
    transcript: "Agent: Metro HVAC.\nUser: My AC just died. I need someone today.\nAgent: Opening in 4 hours. Confirmed at 3 PM today.",
    fields: fields({ customer_name: "Lisa Tran", customer_phone: "+13135550021", service_address: "2015 Mack Ave, Detroit, MI 48207", problem_description: "AC stopped working completely. Emergency same-day repair.", hvac_issue_type: "No Cool", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Trane", equipment_age: "10 years", appointment_booked: true, appointment_datetime: future(4 * HR), callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Urgent", endCallReason: "completed",
    callerType: "residential", primaryIntent: "service", revenueTier: "major_repair", route: "legitimate",
    qualityScore: 9.0, tags: ["booking","confirmed","emergency-repair"], durationSeconds: 143,
    bookingStatus: "confirmed", bookingStatusAt: ago(6 * HR), bookingNotes: "Confirmed by dispatch. Tech en route.",
    createdAt: ago(8 * HR), updatedAt: ago(6 * HR),
  }),
  record({
    callId: "demo-call-022", retellCallId: "retell-demo-022", phone: "+13135550022",
    transcript: "Agent: Metro HVAC.\nUser: I need my old thermostat replaced with a smart one. Any time this week works.\nAgent: Opening in three days. Afternoon slot confirmed.",
    fields: fields({ customer_name: "Robert Kim", customer_phone: "+13135550022", service_address: "5320 W Vernor Hwy, Detroit, MI 48209", problem_description: "Thermostat replacement — upgrading to smart thermostat.", hvac_issue_type: "Thermostat", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Thermostat", equipment_brand: "Honeywell", equipment_age: "12 years", appointment_booked: true, appointment_datetime: future(74 * HR), callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "completed",
    callerType: "residential", primaryIntent: "installation", revenueTier: "minor", route: "legitimate",
    qualityScore: 8.6, tags: ["booking","confirmed","thermostat"], durationSeconds: 158,
    bookingStatus: "confirmed", bookingStatusAt: ago(10 * HR), bookingNotes: "Confirmed for Thursday afternoon.",
    createdAt: ago(12 * HR), updatedAt: ago(10 * HR),
  }),
  record({
    callId: "demo-call-023", retellCallId: "retell-demo-023", phone: "+13135550023",
    transcript: "Agent: Metro HVAC.\nUser: I need to cancel my duct cleaning appointment. Something came up.\nAgent: Appointment cancelled. Please call when you're ready to reschedule.",
    fields: fields({ customer_name: "Angela Foster", customer_phone: "+13135550023", service_address: "1420 Gratiot Ave, Detroit, MI 48207", problem_description: "Duct cleaning appointment cancelled by customer.", hvac_issue_type: "Maintenance", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Ductwork", equipment_brand: null, equipment_age: null, appointment_booked: true, appointment_datetime: future(48 * HR), callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "completed",
    callerType: "residential", primaryIntent: "maintenance", revenueTier: "minor", route: "legitimate",
    qualityScore: 7.3, tags: ["booking","cancelled","duct-cleaning"], durationSeconds: 112,
    bookingStatus: "cancelled", bookingStatusAt: ago(20 * HR), bookingNotes: "Customer cancelled. Schedule conflict.",
    createdAt: ago(1 * DAY), updatedAt: ago(20 * HR),
  }),

  // ── OTHER_AI_HANDLED (5) ───────────────────────────────────────────────────
  record({
    callId: "demo-call-024", retellCallId: "retell-demo-024", phone: "+13135550024",
    transcript: "Agent: Metro HVAC.\nUser: My AC was making a clicking noise but it seems to have stopped. Maybe just a one-time thing.\nAgent: Happy to hear it resolved. Give us a call if it comes back.",
    fields: fields({ customer_name: "Gary Nolan", customer_phone: "+13135550024", service_address: "9812 Fenkell Ave, Detroit, MI 48238", problem_description: "Clicking noise from AC. Resolved on its own before callback.", hvac_issue_type: "Noisy System", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Central AC", equipment_brand: "Carrier", equipment_age: "8 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callbackOutcome: "reached_customer", callbackOutcomeAt: ago(2 * HR),
    callerType: "residential", primaryIntent: "service", revenueTier: "diagnostic", route: "legitimate",
    qualityScore: 7.8, tags: ["handled","resolved","reached-customer"], durationSeconds: 134,
    createdAt: ago(1 * DAY), updatedAt: ago(2 * HR),
  }),
  record({
    callId: "demo-call-025", retellCallId: "retell-demo-025", phone: "+18005550025",
    transcript: "Agent: Metro HVAC.\nUser: Hi, this is National Refrigerants. Calling about your R-410A order.\nAgent: Vendor call. Passing info to our purchasing team.",
    fields: fields({ customer_name: "Vendor Desk", customer_phone: "+18005550025", service_address: null, problem_description: "Vendor call — refrigerant supplier following up on parts order.", hvac_issue_type: null, is_safety_emergency: false, is_urgent_escalation: false, equipment_type: null, equipment_brand: null, equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: "vendor", primaryIntent: "admin_billing", revenueTier: "unknown", route: "vendor",
    qualityScore: 5.0, tags: ["handled","vendor","non-customer"], durationSeconds: 78,
    createdAt: ago(7 * HR), updatedAt: ago(7 * HR),
  }),
  record({
    callId: "demo-call-026", retellCallId: "retell-demo-026", phone: "+13135550026",
    transcript: "Agent: Metro HVAC.\nUser: Wait, this is HVAC? I need a plumber. Wrong number, sorry.\nAgent: No problem! Try searching for a local plumber.",
    fields: fields({ customer_name: "Unknown Caller", customer_phone: "+13135550026", service_address: null, problem_description: "Wrong number — caller needed a plumber, not HVAC.", hvac_issue_type: null, is_safety_emergency: false, is_urgent_escalation: false, equipment_type: null, equipment_brand: null, equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "wrong_number",
    callerType: "unknown", primaryIntent: "unknown", revenueTier: "unknown", route: "legitimate",
    qualityScore: 6.0, tags: ["handled","wrong-number"], durationSeconds: 34,
    createdAt: ago(4 * HR), updatedAt: ago(4 * HR),
  }),
  record({
    callId: "demo-call-027", retellCallId: "retell-demo-027", phone: "+18885550027",
    transcript: "Agent: Metro HVAC.\nUser: Congratulations! You've been selected for a special—\nAgent: Automated call detected. Ending session.",
    fields: fields({ customer_name: "Robo Dialer", customer_phone: "+18885550027", service_address: null, problem_description: "Spam robocall. Extraction failed.", hvac_issue_type: null, is_safety_emergency: false, is_urgent_escalation: false, equipment_type: null, equipment_brand: null, equipment_age: null, appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "failed", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callerType: "spam", primaryIntent: "solicitation", revenueTier: "unknown", route: "spam",
    qualityScore: 1.0, tags: ["handled","spam","extraction-failed"], durationSeconds: 18,
    createdAt: ago(6 * HR), updatedAt: ago(6 * HR),
  }),
  record({
    callId: "demo-call-028", retellCallId: "retell-demo-028", phone: "+13135550028",
    transcript: "Agent: Metro HVAC.\nUser: Actually, my neighbor ended up fixing the issue for me. I don't need a tech anymore.\nAgent: Great to hear! Noted as resolved.",
    fields: fields({ customer_name: "David Park", customer_phone: "+13135550028", service_address: "4410 W Chicago Ave, Detroit, MI 48204", problem_description: "Resolved by neighbor before tech visit. Closing call.", hvac_issue_type: "No Heat", is_safety_emergency: false, is_urgent_escalation: false, equipment_type: "Furnace", equipment_brand: "Carrier", equipment_age: "7 years", appointment_booked: false, appointment_datetime: null, callback_type: null, callback_window_start: null, callback_window_end: null }),
    extractionStatus: "complete", urgencyTier: "Routine", endCallReason: "customer_hangup",
    callbackOutcome: "resolved_elsewhere", callbackOutcomeAt: ago(3 * HR),
    callerType: "residential", primaryIntent: "service", revenueTier: "minor", route: "legitimate",
    qualityScore: 7.6, tags: ["handled","resolved-elsewhere"], durationSeconds: 89,
    createdAt: ago(18 * HR), updatedAt: ago(3 * HR),
  }),
];

const { error: insertErr } = await supabase.from("call_records").insert(records);
if (insertErr) { console.error("Insert failed:", insertErr); process.exit(1); }
console.log(`  ✓ Inserted ${records.length} records`);

// callback_touches are not exposed via PostgREST.
// The log_callback_touch trigger on call_records automatically inserts one touch
// per record where callback_outcome is set, using callback_outcome_at as the timestamp.
// That covers all 8 follow-up/handled calls with the correct timestamps.
console.log("Step 3: callback_touches auto-seeded by trigger (not accessible via PostgREST)");

console.log("\n✅ Seed complete. Reload the app to see the new data.");
