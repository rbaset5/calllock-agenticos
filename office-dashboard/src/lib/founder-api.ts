export type FounderArtifactRef = {
  id: string | null;
  artifact_type: string | null;
  run_id: string | null;
  created_at: string | null;
};

export type FounderApprovalItem = {
  id: string | null;
  title: string;
  affected_surface: string;
  risk_level: string;
  reason: string;
  requested_action: string;
  age: string;
  evidence_summary: string;
  recommended_action: string;
  source: string;
  run_id: string | null;
};

export type FounderBlockedWorkItem = {
  id: string | null;
  worker_id: string | null;
  task_type: string | null;
  state: string;
  blocked_reason: string;
  recommended_next_step: string | null;
  artifact_refs: FounderArtifactRef[];
};

export type FounderIssueThread = {
  incident_id: string;
  incident_key: string;
  workflow_status: string | null;
  severity: string | null;
  current_alert_id: string | null;
  alert_type: string | null;
  incident_domain: string | null;
  incident_category: string | null;
  notification_outcome: string;
};

export type FounderIssuePosture = {
  counts: {
    open_threads: number;
    founder_visible_threads: number;
  };
  active_threads: FounderIssueThread[];
};

export type FounderActivePriority = {
  label: string | null;
  constraints: string[];
  source: string;
};

export type FounderVoiceTruthSummary = {
  state: string;
  top_reason: string;
  last_evaluated_at: string | null;
  failed_metric_count: number;
  baseline_version: string | null;
  candidate_version: string | null;
  artifact_refs: FounderArtifactRef[];
};

export type FounderHomeResponse = {
  briefing: {
    generated_at: string;
    top_change:
      | FounderApprovalItem
      | FounderBlockedWorkItem
      | FounderIssueThread
      | FounderVoiceTruthSummary
      | null;
    top_regression: FounderVoiceTruthSummary | null;
    top_issue_thread: FounderIssueThread | null;
    top_blocked_work: FounderBlockedWorkItem | null;
    top_pending_approval: FounderApprovalItem | null;
    recommended_action: string;
    active_priority: FounderActivePriority;
  };
  voice_truth: FounderVoiceTruthSummary;
  issue_posture: FounderIssuePosture;
  active_priority: FounderActivePriority;
};

export type FounderApprovalsResponse = {
  items: FounderApprovalItem[];
};

export type FounderBlockedWorkResponse = {
  items: FounderBlockedWorkItem[];
};

export type FounderApprovalDecisionStatus =
  | "approved"
  | "rejected"
  | "cancelled";

export type ResolveFounderApprovalPayload = {
  status: FounderApprovalDecisionStatus;
  resolution_notes: string;
};

export type FounderApprovalDecisionResponse = {
  id?: string;
  status?: FounderApprovalDecisionStatus;
  resolved_by?: string | null;
  resolution_notes?: string | null;
  continuation?: {
    mode?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

type FounderTenantRequest = {
  tenantId?: string | null;
};

type ProxyFounderRequestOptions = {
  body?: BodyInit | null;
  headers?: HeadersInit;
  method?: "GET" | "POST";
  tenantId?: string | null;
};

function getFounderApiBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_HARNESS_BASE_URL?.trim();

  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_HARNESS_BASE_URL is required");
  }

  return baseUrl.replace(/\/+$/, "");
}

function buildFounderApiUrl(
  path: string,
  query: Record<string, string | null | undefined> = {}
) {
  const url = new URL(path, `${getFounderApiBaseUrl()}/`);

  for (const [key, value] of Object.entries(query)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }

  return url;
}

function mergeHeaders(...headerSets: Array<HeadersInit | undefined>) {
  const headers = new Headers();

  for (const headerSet of headerSets) {
    if (!headerSet) {
      continue;
    }

    const resolvedHeaders = new Headers(headerSet);
    resolvedHeaders.forEach((value, key) => {
      headers.set(key, value);
    });
  }

  return headers;
}

async function fetchFounderApi(path: string, options: ProxyFounderRequestOptions = {}) {
  const { body, headers, method = "GET", tenantId } = options;

  return fetch(buildFounderApiUrl(path, { tenant_id: tenantId }), {
    method,
    headers,
    body,
    cache: "no-store",
  });
}

async function fetchFounderJson<T>(
  path: string,
  options: ProxyFounderRequestOptions = {}
) {
  const response = await fetchFounderApi(path, options);

  if (!response.ok) {
    throw new Error(`Founder API request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchFounderHome(options: FounderTenantRequest = {}) {
  return fetchFounderJson<FounderHomeResponse>("/founder/home", {
    tenantId: options.tenantId,
  });
}

export async function fetchFounderApprovals(options: FounderTenantRequest = {}) {
  return fetchFounderJson<FounderApprovalsResponse>("/founder/approvals", {
    tenantId: options.tenantId,
  });
}

export async function fetchFounderBlockedWork(
  options: FounderTenantRequest = {}
) {
  return fetchFounderJson<FounderBlockedWorkResponse>("/founder/blocked-work", {
    tenantId: options.tenantId,
  });
}

export async function resolveFounderApproval(
  approvalId: string,
  payload: ResolveFounderApprovalPayload,
  headers?: HeadersInit
) {
  return fetchFounderJson<FounderApprovalDecisionResponse>(
    `/approvals/${encodeURIComponent(approvalId)}`,
    {
      method: "POST",
      headers: mergeHeaders(
        {
          "content-type": "application/json",
        },
        headers
      ),
      body: JSON.stringify(payload),
    }
  );
}

export async function proxyFounderRequest(
  path: string,
  options: ProxyFounderRequestOptions = {}
) {
  return fetchFounderApi(path, options);
}

export async function createFounderProxyResponse(upstream: Response) {
  const body = await upstream.text();
  const headers = new Headers();

  headers.set(
    "content-type",
    upstream.headers.get("content-type") ?? "application/json"
  );
  headers.set("cache-control", "no-store");

  return new Response(body, {
    status: upstream.status,
    headers,
  });
}
