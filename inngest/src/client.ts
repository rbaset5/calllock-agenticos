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

export interface HarnessRequestConfig extends HarnessDispatchConfig {
  path: string;
  method?: "GET" | "POST";
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

export async function dispatchHarnessRequest(
  config: HarnessRequestConfig,
  payload?: Record<string, unknown>,
  fetchImpl: typeof fetch = fetch,
) {
  const response = await fetchImpl(`${config.baseUrl}${config.path}`, {
    method: config.method ?? "POST",
    headers: {
      "Content-Type": "application/json",
      ...(config.eventSecret ? { Authorization: `Bearer ${config.eventSecret}` } : {}),
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  if (!response.ok) {
    throw new Error(`Harness request failed with status ${response.status}`);
  }

  return response.json();
}
