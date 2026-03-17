import { describe, expect, it } from "vitest";

import { type CallEndedPayload, validateProcessCallPayload } from "../events/schemas.js";
import {
  SEND_EMERGENCY_SMS_IDEMPOTENCY,
  buildEmergencySmsIdempotencyKey,
  voiceEventToProcessCall,
} from "../functions/voice.js";

function createCallEndedPayload(overrides: Partial<CallEndedPayload> = {}): CallEndedPayload {
  return {
    tenant_id: "tenant-123",
    call_id: "call-456",
    call_source: "retell",
    phone_number: "+15125550101",
    transcript: "Customer says there is a gas leak in the attic.",
    customer_name: "Jane Smith",
    service_address: "123 Oak St, Austin, TX 78701",
    problem_description: "Gas leak in attic",
    urgency_tier: "emergency",
    caller_type: "residential",
    primary_intent: "service",
    revenue_tier: "standard_repair",
    tags: ["SAFETY_GAS_LEAK"],
    quality_score: 92,
    scorecard_warnings: [],
    route: "legitimate",
    booking_id: null,
    callback_scheduled: false,
    extraction_status: "complete",
    retell_call_id: "ret-789",
    call_duration_seconds: 180,
    end_call_reason: "safety_exit",
    call_recording_url: "https://retell.ai/recording/ret-789.mp3",
    ...overrides,
  };
}

describe("voiceEventToProcessCall", () => {
  it("maps call_metadata and stays compatible with ProcessCallRequest extra=forbid", () => {
    const payload = createCallEndedPayload();
    const mapped = voiceEventToProcessCall(payload);

    expect(mapped).toEqual({
      call_id: "call-456",
      tenant_id: "tenant-123",
      transcript: "Customer says there is a gas leak in the attic.",
      problem_description: "Gas leak in attic",
      call_source: "retell",
      call_metadata: {
        voice_event: true,
        route: "legitimate",
      },
    });
    expect("call_metadata" in mapped).toBe(true);
    expect("metadata" in (mapped as unknown as Record<string, unknown>)).toBe(false);
    expect(validateProcessCallPayload(mapped)).toEqual([]);
    expect(Object.keys(mapped).sort()).toEqual(
      ["call_id", "tenant_id", "transcript", "problem_description", "call_source", "call_metadata"].sort(),
    );
  });
});

describe("send-emergency-sms", () => {
  it("uses the required tenant_id:call_id:emergency-sms idempotency format", () => {
    const payload = createCallEndedPayload();

    expect(buildEmergencySmsIdempotencyKey(payload)).toBe("tenant-123:call-456:emergency-sms");
    expect(SEND_EMERGENCY_SMS_IDEMPOTENCY).toContain("event.data.tenant_id");
    expect(SEND_EMERGENCY_SMS_IDEMPOTENCY).toContain("event.data.call_id");
    expect(SEND_EMERGENCY_SMS_IDEMPOTENCY).toContain(":emergency-sms");
  });
});

