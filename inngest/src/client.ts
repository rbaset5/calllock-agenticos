export interface HarnessTriggerEvent {
  name: "harness/process-call";
  data: {
    call_id: string;
    tenant_id: string;
    transcript?: string;
    problem_description?: string;
  };
}

export function buildHarnessEvent(data: HarnessTriggerEvent["data"]): HarnessTriggerEvent {
  return { name: "harness/process-call", data };
}

export interface HarnessDispatchConfig {
  baseUrl: string;
  eventSecret?: string;
}

export async function dispatchHarnessEvent(
  config: HarnessDispatchConfig,
  event: HarnessTriggerEvent,
  fetchImpl: typeof fetch = fetch,
) {
  const response = await fetchImpl(`${config.baseUrl}/events/process-call`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(config.eventSecret ? { Authorization: `Bearer ${config.eventSecret}` } : {}),
    },
    body: JSON.stringify(event),
  });

  if (!response.ok) {
    throw new Error(`Harness event dispatch failed with status ${response.status}`);
  }

  return response.json();
}
