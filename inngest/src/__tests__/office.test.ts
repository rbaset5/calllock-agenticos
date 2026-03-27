import { describe, expect, it, vi } from "vitest";

import {
  agentStateChangedToOfficeRow,
  syncAgentOfficeStateTask,
} from "../functions/office.js";

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
