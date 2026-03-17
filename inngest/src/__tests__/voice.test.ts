import { describe, expect, it, vi } from "vitest";

import { type CallEndedPayload, validateProcessCallPayload } from "../events/schemas.js";
import {
  SEND_EMERGENCY_SMS_IDEMPOTENCY,
  VOICE_HARNESS_PATHS,
  buildEmergencySmsIdempotencyKey,
  syncAppTask,
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

function createFetchResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
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

describe("syncAppTask", () => {
  it("sets synced_to_app=true after a successful app sync", async () => {
    process.env.HARNESS_BASE_URL = "https://harness.example.com";
    process.env.HARNESS_EVENT_SECRET = "top-secret";

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(createFetchResponse(200, { delivered: true }))
      .mockResolvedValueOnce(createFetchResponse(200, { updated: true }));

    const result = await syncAppTask(createCallEndedPayload(), fetchMock as typeof fetch);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://harness.example.com/voice/sync-app",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://harness.example.com/voice/call-records/mark-synced",
      expect.objectContaining({ method: "POST" }),
    );

    const secondCall = fetchMock.mock.calls[1];
    const secondBody = JSON.parse((secondCall?.[1] as RequestInit).body as string);
    expect(secondBody).toEqual({
      tenant_id: "tenant-123",
      call_id: "call-456",
      synced_to_app: true,
    });
    expect(result.synced_to_app).toBe(true);
  });

  it("does not set synced_to_app when the app sync fails", async () => {
    process.env.HARNESS_BASE_URL = "https://harness.example.com";
    process.env.HARNESS_EVENT_SECRET = "top-secret";

    const fetchMock = vi.fn().mockResolvedValueOnce(createFetchResponse(503, { error: "app unavailable" }));

    await expect(syncAppTask(createCallEndedPayload(), fetchMock as typeof fetch)).rejects.toThrow(
      "Harness request failed with status 503",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://harness.example.com/voice/sync-app",
      expect.objectContaining({ method: "POST" }),
    );
    expect(VOICE_HARNESS_PATHS.markSynced).toBe("/voice/call-records/mark-synced");
  });
});
