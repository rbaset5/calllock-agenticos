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

type LocalFounderRequestOptions = {
  body?: BodyInit | null;
  headers?: HeadersInit;
  method?: "GET" | "POST";
};

type FounderEndpointConfig = {
  localPath: string;
  upstreamPath: string;
};

type UpstreamFounderRequestOptions = {
  body?: BodyInit | null;
  headers?: HeadersInit;
  method?: "GET" | "POST";
  tenantId?: string | null;
};

const JSON_CONTENT_TYPE = "application/json";
const FORWARDED_UPSTREAM_HEADERS = [
  "content-type",
  "retry-after",
  "x-request-id",
  "x-correlation-id",
  "traceparent",
] as const;

export const founderEndpoints = {
  home: {
    localPath: "/api/founder/home",
    upstreamPath: "/founder/home",
  },
  approvals: {
    localPath: "/api/founder/approvals",
    upstreamPath: "/founder/approvals",
  },
  blockedWork: {
    localPath: "/api/founder/blocked-work",
    upstreamPath: "/founder/blocked-work",
  },
} satisfies Record<string, FounderEndpointConfig>;

function getFounderApprovalLocalPath(approvalId: string) {
  return `${founderEndpoints.approvals.localPath}/${encodeURIComponent(approvalId)}`;
}

function getFounderApprovalUpstreamPath(approvalId: string) {
  return `/approvals/${encodeURIComponent(approvalId)}`;
}

function getFounderHarnessBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_HARNESS_BASE_URL?.trim();

  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_HARNESS_BASE_URL is required");
  }

  return baseUrl.replace(/\/+$/, "");
}

function buildFounderUpstreamUrl(
  path: string,
  query: Record<string, string | null | undefined> = {}
) {
  const url = new URL(path, `${getFounderHarnessBaseUrl()}/`);

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

function buildFounderLocalUrl(
  path: string,
  query: Record<string, string | null | undefined> = {}
) {
  const url = new URL(path, "http://localhost");

  for (const [key, value] of Object.entries(query)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }

  return `${url.pathname}${url.search}`;
}

async function fetchFounderUpstream(
  path: string,
  options: UpstreamFounderRequestOptions = {}
) {
  const { body, headers, method = "GET", tenantId } = options;

  return fetch(buildFounderUpstreamUrl(path, { tenant_id: tenantId }), {
    method,
    headers,
    body,
    cache: "no-store",
  });
}

async function fetchFounderLocal(
  path: string,
  options: LocalFounderRequestOptions = {}
) {
  const { body, headers, method = "GET" } = options;

  return fetch(path, {
    method,
    headers,
    body,
    cache: "no-store",
  });
}

async function fetchFounderJson<T>(
  responsePromise: Promise<Response>
) {
  const response = await responsePromise;
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes(JSON_CONTENT_TYPE);
  const payload = isJson
    ? ((await response.json()) as T | { error?: string })
    : await response.text();

  if (!response.ok) {
    if (typeof payload === "string") {
      throw new Error(payload || `Founder API request failed with status ${response.status}`);
    }

    const errorMessage =
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : `Founder API request failed with status ${response.status}`;

    throw new Error(
      errorMessage
    );
  }

  return payload as T;
}

export async function fetchFounderHome(options: FounderTenantRequest = {}) {
  return fetchFounderJson<FounderHomeResponse>(
    fetchFounderLocal(
      buildFounderLocalUrl(founderEndpoints.home.localPath, {
        tenant_id: options.tenantId,
      })
    )
  );
}

export async function fetchFounderApprovals(options: FounderTenantRequest = {}) {
  return fetchFounderJson<FounderApprovalsResponse>(
    fetchFounderLocal(
      buildFounderLocalUrl(founderEndpoints.approvals.localPath, {
        tenant_id: options.tenantId,
      })
    )
  );
}

export async function fetchFounderBlockedWork(
  options: FounderTenantRequest = {}
) {
  return fetchFounderJson<FounderBlockedWorkResponse>(
    fetchFounderLocal(
      buildFounderLocalUrl(founderEndpoints.blockedWork.localPath, {
        tenant_id: options.tenantId,
      })
    )
  );
}

export async function resolveFounderApproval(
  approvalId: string,
  payload: ResolveFounderApprovalPayload,
  headers?: HeadersInit
) {
  return fetchFounderJson<FounderApprovalDecisionResponse>(
    fetchFounderLocal(getFounderApprovalLocalPath(approvalId), {
      method: "POST",
      headers: mergeHeaders(
        {
          "content-type": JSON_CONTENT_TYPE,
        },
        headers
      ),
      body: JSON.stringify(payload),
    })
  );
}

function copyFounderUpstreamHeaders(upstream: Response) {
  const headers = new Headers({
    "cache-control": "no-store",
  });

  for (const headerName of FORWARDED_UPSTREAM_HEADERS) {
    const value = upstream.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }

  if (!headers.has("content-type")) {
    headers.set("content-type", JSON_CONTENT_TYPE);
  }

  return headers;
}

function createFounderJsonResponse(
  payload: Record<string, unknown>,
  status: number
) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "cache-control": "no-store",
      "content-type": JSON_CONTENT_TYPE,
    },
  });
}

function createFounderProxyErrorResponse(error: unknown) {
  if (
    error instanceof Error &&
    error.message === "NEXT_PUBLIC_HARNESS_BASE_URL is required"
  ) {
    return createFounderJsonResponse({ error: error.message }, 500);
  }

  return createFounderJsonResponse(
    {
      error:
        error instanceof Error
          ? error.message
          : "Failed to reach founder upstream",
    },
    502
  );
}

export async function requestFounderUpstream(
  path: string,
  options: UpstreamFounderRequestOptions = {}
) {
  return fetchFounderUpstream(path, options);
}

export async function createFounderProxyResponse(upstream: Response) {
  const body = await upstream.text();

  return new Response(body, {
    status: upstream.status,
    headers: copyFounderUpstreamHeaders(upstream),
  });
}

export async function proxyFounderEndpoint(
  request: Request,
  endpoint: FounderEndpointConfig
) {
  try {
    const url = new URL(request.url);
    const upstream = await requestFounderUpstream(endpoint.upstreamPath, {
      tenantId: url.searchParams.get("tenant_id"),
    });

    return createFounderProxyResponse(upstream);
  } catch (error) {
    return createFounderProxyErrorResponse(error);
  }
}

export async function proxyFounderApprovalDecision(
  request: Request,
  approvalId: string
) {
  try {
    const headers = new Headers();

    headers.set(
      "content-type",
      request.headers.get("content-type") ?? JSON_CONTENT_TYPE
    );

    headers.set("x-actor-id", request.headers.get("x-actor-id") ?? "founder");

    const upstream = await requestFounderUpstream(
      getFounderApprovalUpstreamPath(approvalId),
      {
        method: "POST",
        body: await request.text(),
        headers,
      }
    );

    return createFounderProxyResponse(upstream);
  } catch (error) {
    return createFounderProxyErrorResponse(error);
  }
}
