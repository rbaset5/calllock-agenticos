export interface HarnessTriggerEvent {
  name: "harness/process-call" | "harness/job-complete";
  data: Record<string, unknown>;
}

export function buildHarnessEvent(data: Record<string, unknown>): HarnessTriggerEvent {
  return { name: "harness/process-call", data };
}

export function buildJobCompleteEvent(data: Record<string, unknown>): HarnessTriggerEvent {
  return { name: "harness/job-complete", data };
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
  const endpoint = event.name === "harness/job-complete" ? "/events/job-complete" : "/events/process-call";
  const response = await fetchImpl(`${config.baseUrl}${endpoint}`, {
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
