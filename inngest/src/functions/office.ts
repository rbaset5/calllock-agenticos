import {
  AGENT_DISPATCH,
  AGENT_STATE_CHANGED,
  type AgentDispatchPayload,
  type AgentStateChangedPayload,
  validateAgentDispatchPayload,
  validateAgentStateChangedPayload,
} from "../events/schemas.js";
import { buildHarnessEvent, dispatchHarnessEvent } from "../client.js";
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

function assertValidAgentDispatchPayload(payload: AgentDispatchPayload) {
  const errors = validateAgentDispatchPayload(payload);
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

export function agentDispatchToHarnessPayload(payload: AgentDispatchPayload) {
  return {
    call_id: `dispatch:${payload.idempotency_key}`,
    tenant_id: payload.tenant_id,
    worker_id: payload.worker_id,
    transcript: "",
    problem_description: payload.task_type,
    call_source: "manual",
    task_context: {
      ...payload.task_context,
      dispatch_metadata: {
        origin_worker_id: payload.origin_worker_id,
        idempotency_key: payload.idempotency_key,
        priority: payload.priority ?? "medium",
      },
    },
    job_requests: [],
  };
}

export function agentDispatchToIdleEvent(payload: AgentDispatchPayload): AgentStateChangedPayload {
  return {
    agent_id: payload.worker_id,
    tenant_id: payload.tenant_id,
    department: payload.department,
    role: payload.role,
    from_state: "worker",
    to_state: "idle",
    description: payload.description ?? payload.task_type,
  };
}

export async function dispatchAgentTaskTask(
  payload: AgentDispatchPayload,
  fetchImpl: typeof fetch = fetch,
  sendEventImpl: (event: { name: string; data: AgentStateChangedPayload }) => Promise<unknown> = (event) =>
    inngest.send(event),
) {
  assertValidAgentDispatchPayload(payload);
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }

  const result = await dispatchHarnessEvent(
    {
      baseUrl,
      eventSecret: process.env.HARNESS_EVENT_SECRET,
    },
    buildHarnessEvent(agentDispatchToHarnessPayload(payload)),
    fetchImpl,
  );

  await sendEventImpl({
    name: AGENT_STATE_CHANGED,
    data: agentDispatchToIdleEvent(payload),
  });

  return result;
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

export const dispatchAgentTask = inngest.createFunction(
  { id: "dispatch-agent-task" },
  { event: AGENT_DISPATCH },
  async ({ event, step }: any) => {
    return step.run("dispatch-agent-task", async () =>
      dispatchAgentTaskTask(event.data as AgentDispatchPayload),
    );
  },
);
