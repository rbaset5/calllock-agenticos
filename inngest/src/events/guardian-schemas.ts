/**
 * Event emitted by eng-product-qa to dispatch surface agents.
 * eng-product-qa has role:worker so it cannot use the supervisor's
 * job dispatch path directly. Instead it emits this event, which
 * triggers an Inngest function that calls the harness for the target agent.
 */
export interface GuardianDispatchPayload {
  /** Target worker_id: "eng-app" or "eng-ai-voice" */
  target: string;
  /** Task to execute: "app-pr-validation", "voice-pr-validation" */
  task_type: string;
  /** PR number if triggered by a PR */
  pr_id?: number;
  /** PR URL for context */
  pr_url?: string;
  /** Additional context for the target agent */
  task_context: Record<string, unknown>;
  /** Always "eng-product-qa" */
  origin: "eng-product-qa";
  /** Tenant scope (UUID) */
  tenant_id: string;
  /** Dispatch timeout in ms (default 300000 = 5 min) */
  timeout_ms: number;
}

/**
 * Watchdog check payload — emitted by cron, checks that all
 * guardian agents reported today.
 */
export interface GuardianWatchdogPayload {
  /** Date to check reports for (YYYY-MM-DD) */
  check_date: string;
  /** Tenant scope (UUID) */
  tenant_id: string;
}
