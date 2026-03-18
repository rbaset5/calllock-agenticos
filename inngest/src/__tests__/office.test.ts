import { describe, expect, it, vi } from "vitest";

import {
  agentDispatchToHarnessPayload,
  agentDispatchToIdleEvent,
  agentStateChangedToOfficeRow,
  dispatchAgentTaskTask,
  syncAgentOfficeStateTask,
} from "../functions/office.js";
import { AGENT_STATE_CHANGED } from "../events/schemas.js";

function createAgentStateChangedPayload() {
  return {
    agent_id: "eng-ai-voice",
    tenant_id: "tenant-123",
    department: "engineering",
    role: "worker",
    from_state: "policy_gate",
    to_state: "verification",
    description: "AI/Voice Engineer",
  } as const;
}

function createAgentDispatchPayload() {
  return {
    worker_id: "eng-ai-voice",
    tenant_id: "tenant-123",
    origin_worker_id: "eng-vp",
    department: "engineering",
    role: "worker",
    task_type: "investigate-call",
    task_context: { call_id: "4821" },
    idempotency_key: "dispatch-4821",
    priority: "high",
    description: "AI/Voice Engineer",
  } as const;
}

describe("agentStateChangedToOfficeRow", () => {
  it("maps the event into the agent_office_state schema", () => {
    const row = agentStateChangedToOfficeRow(
      createAgentStateChangedPayload(),
      "2026-03-18T12:00:00.000Z",
    );

    expect(row).toEqual({
      agent_id: "eng-ai-voice",
      tenant_id: "tenant-123",
      department: "engineering",
      role: "worker",
      current_state: "verification",
      description: "AI/Voice Engineer",
      updated_at: "2026-03-18T12:00:00.000Z",
    });
  });
});

describe("syncAgentOfficeStateTask", () => {
  it("upserts into Supabase via REST", async () => {
    process.env.SUPABASE_URL = "https://supabase.example.co";
    process.env.SUPABASE_SERVICE_ROLE_KEY = "service-role-key";

    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ agent_id: "eng-ai-voice" }],
    });

    const result = await syncAgentOfficeStateTask(
      createAgentStateChangedPayload(),
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://supabase.example.co/rest/v1/agent_office_state?on_conflict=tenant_id,agent_id",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          apikey: "service-role-key",
          Authorization: "Bearer service-role-key",
          Prefer: "resolution=merge-duplicates,return=representation",
        }),
      }),
    );
    expect(result).toEqual([{ agent_id: "eng-ai-voice" }]);
  });

  it("rejects invalid payloads before calling Supabase", async () => {
    process.env.SUPABASE_URL = "https://supabase.example.co";
    process.env.SUPABASE_SERVICE_ROLE_KEY = "service-role-key";

    const fetchImpl = vi.fn();

    await expect(
      syncAgentOfficeStateTask(
        { ...createAgentStateChangedPayload(), tenant_id: "" },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("tenant_id is required");

    expect(fetchImpl).not.toHaveBeenCalled();
  });
});

describe("agentDispatchToHarnessPayload", () => {
  it("maps dispatch events into a harness process-call request", () => {
    expect(agentDispatchToHarnessPayload(createAgentDispatchPayload())).toEqual({
      call_id: "dispatch:dispatch-4821",
      tenant_id: "tenant-123",
      worker_id: "eng-ai-voice",
      transcript: "",
      problem_description: "investigate-call",
      call_source: "manual",
      task_context: {
        call_id: "4821",
        dispatch_metadata: {
          origin_worker_id: "eng-vp",
          idempotency_key: "dispatch-4821",
          priority: "high",
        },
      },
      job_requests: [],
    });
  });
});

describe("agentDispatchToIdleEvent", () => {
  it("builds the idle state event after the worker run completes", () => {
    expect(agentDispatchToIdleEvent(createAgentDispatchPayload())).toEqual({
      agent_id: "eng-ai-voice",
      tenant_id: "tenant-123",
      department: "engineering",
      role: "worker",
      from_state: "worker",
      to_state: "idle",
      description: "AI/Voice Engineer",
    });
  });
});

describe("dispatchAgentTaskTask", () => {
  it("forwards to the harness and emits idle state afterward", async () => {
    process.env.HARNESS_BASE_URL = "https://harness.example";
    process.env.HARNESS_EVENT_SECRET = "secret";

    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ run_id: "run-1" }),
    });
    const sendEventImpl = vi.fn().mockResolvedValue(undefined);

    const result = await dispatchAgentTaskTask(
      createAgentDispatchPayload(),
      fetchImpl as unknown as typeof fetch,
      sendEventImpl,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://harness.example/events/process-call",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer secret",
        }),
      }),
    );
    expect(JSON.parse(fetchImpl.mock.calls[0]?.[1]?.body as string)).toEqual({
      name: "harness/process-call",
      data: agentDispatchToHarnessPayload(createAgentDispatchPayload()),
    });
    expect(sendEventImpl).toHaveBeenCalledWith({
      name: AGENT_STATE_CHANGED,
      data: agentDispatchToIdleEvent(createAgentDispatchPayload()),
    });
    expect(result).toEqual({ run_id: "run-1" });
  });

  it("rejects invalid payloads before dispatching", async () => {
    process.env.HARNESS_BASE_URL = "https://harness.example";

    const fetchImpl = vi.fn();
    const sendEventImpl = vi.fn();

    await expect(
      dispatchAgentTaskTask(
        { ...createAgentDispatchPayload(), worker_id: "" },
        fetchImpl as unknown as typeof fetch,
        sendEventImpl,
      ),
    ).rejects.toThrow("worker_id is required");

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(sendEventImpl).not.toHaveBeenCalled();
  });
});
