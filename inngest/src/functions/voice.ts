import { buildHarnessEvent, dispatchHarnessEvent, dispatchHarnessRequest } from "../client.js";
import {
  CALL_ENDED,
  type CallEndedPayload,
  type ProcessCallPayload,
  validateCallEndedPayload,
  validateProcessCallPayload,
} from "../events/schemas.js";
import { inngest } from "../inngest.js";

export const VOICE_HARNESS_PATHS = {
  emergencySms: "/voice/emergency-sms",
  callRecordsRetention: "/voice/call-records/retention",
} as const;

export const SEND_EMERGENCY_SMS_IDEMPOTENCY =
  "event.data.tenant_id + ':' + event.data.call_id + ':emergency-sms'";

function getHarnessConfig() {
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }
  return {
    baseUrl,
    eventSecret: process.env.HARNESS_EVENT_SECRET,
  };
}

function assertValidCallEndedPayload(payload: CallEndedPayload) {
  const errors = validateCallEndedPayload(payload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }
}

export function voiceEventToProcessCall(payload: CallEndedPayload): ProcessCallPayload {
  const mappedPayload: ProcessCallPayload = {
    call_id: payload.call_id,
    tenant_id: payload.tenant_id,
    transcript: payload.transcript,
    call_source: "retell",
    call_metadata: {
      voice_event: true,
      route: payload.route,
    },
    ...(payload.problem_description ? { problem_description: payload.problem_description } : {}),
  };

  const errors = validateProcessCallPayload(mappedPayload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }

  return mappedPayload;
}

export function buildEmergencySmsIdempotencyKey(payload: Pick<CallEndedPayload, "tenant_id" | "call_id">): string {
  return `${payload.tenant_id}:${payload.call_id}:emergency-sms`;
}

export function isSafetyEmergency(payload: CallEndedPayload): boolean {
  return payload.urgency_tier === "emergency" || payload.end_call_reason === "safety_exit";
}

export async function processVoiceCallTask(payload: CallEndedPayload, fetchImpl: typeof fetch = fetch) {
  assertValidCallEndedPayload(payload);
  return dispatchHarnessEvent(
    getHarnessConfig(),
    buildHarnessEvent(voiceEventToProcessCall(payload) as unknown as Record<string, unknown>),
    fetchImpl,
  );
}

export async function sendEmergencySmsTask(payload: CallEndedPayload, fetchImpl: typeof fetch = fetch) {
  assertValidCallEndedPayload(payload);
  if (!isSafetyEmergency(payload)) {
    return {
      skipped: true,
      reason: "not_safety_emergency",
    };
  }

  return dispatchHarnessRequest(
    {
      ...getHarnessConfig(),
      path: VOICE_HARNESS_PATHS.emergencySms,
    },
    {
      ...(payload as unknown as Record<string, unknown>),
      idempotency_key: buildEmergencySmsIdempotencyKey(payload),
    },
    fetchImpl,
  );
}

export async function callRecordsRetentionTask(fetchImpl: typeof fetch = fetch) {
  return dispatchHarnessRequest(
    {
      ...getHarnessConfig(),
      path: VOICE_HARNESS_PATHS.callRecordsRetention,
    },
    {
      purge_transcripts: true,
      delete_expired_rows: true,
    },
    fetchImpl,
  );
}

export const processVoiceCall = inngest.createFunction(
  { id: "process-voice-call" },
  { event: CALL_ENDED },
  async ({ event, step }: any) => {
    return step.run("dispatch-process-call", async () => processVoiceCallTask(event.data as CallEndedPayload));
  },
);

export const sendEmergencySms = inngest.createFunction(
  { id: "send-emergency-sms", idempotency: SEND_EMERGENCY_SMS_IDEMPOTENCY, retries: 3 },
  { event: CALL_ENDED },
  async ({ event, step }: any) => {
    return step.run("send-emergency-sms", async () => sendEmergencySmsTask(event.data as CallEndedPayload));
  },
);

export const callRecordsRetention = inngest.createFunction(
  { id: "call-records-retention" },
  { cron: "0 5 * * 0" },
  async ({ step }: any) => {
    return step.run("cleanup-call-records", async () => callRecordsRetentionTask());
  },
);
