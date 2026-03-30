import {
  AGENT_STATE_CHANGED,
  type AgentStateChangedPayload,
  validateAgentStateChangedPayload,
} from "../events/schemas.js";
import { inngest } from "../inngest.js";

export interface AgentOfficeStateRow {
  agent_id: string;
  tenant_id: string;
  department: string;
  role: string;
  current_state: string;
  description: string | null;
  updated_at: string;
}

function getSupabaseConfig() {
  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required");
  }
  return {
    supabaseUrl: supabaseUrl.replace(/\/$/, ""),
    serviceRoleKey,
  };
}

function assertValidAgentStateChangedPayload(payload: AgentStateChangedPayload) {
  const errors = validateAgentStateChangedPayload(payload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }
}

export function agentStateChangedToOfficeRow(
  payload: AgentStateChangedPayload,
  nowIso: string = new Date().toISOString(),
): AgentOfficeStateRow {
  return {
    agent_id: payload.agent_id,
    tenant_id: payload.tenant_id,
    department: payload.department,
    role: payload.role,
    current_state: payload.to_state,
    description: payload.description ?? null,
    updated_at: nowIso,
  };
}

export async function syncAgentOfficeStateTask(
  payload: AgentStateChangedPayload,
  fetchImpl: typeof fetch = fetch,
) {
  assertValidAgentStateChangedPayload(payload);
  const { supabaseUrl, serviceRoleKey } = getSupabaseConfig();
  const row = agentStateChangedToOfficeRow(payload);

  const response = await fetchImpl(
    `${supabaseUrl}/rest/v1/agent_office_state?on_conflict=tenant_id,agent_id`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        Prefer: "resolution=merge-duplicates,return=representation",
      },
      body: JSON.stringify(row),
    },
  );

  if (!response.ok) {
    throw new Error(`Agent office state sync failed with status ${response.status}`);
  }

  return response.json();
}

export const syncAgentOfficeState = inngest.createFunction(
  { id: "sync-agent-office-state" },
  { event: AGENT_STATE_CHANGED },
  async ({ event, step }: any) => {
    return step.run("upsert-agent-office-state", async () =>
      syncAgentOfficeStateTask(event.data as AgentStateChangedPayload),
    );
  },
);
