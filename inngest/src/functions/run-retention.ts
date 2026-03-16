import { inngest } from "../inngest.js";

type DueTenant = {
  id: string;
  tenant_id: string;
  tenant_slug?: string;
  timezone: string;
  local_hour: number;
  local_minute: number;
  scheduled_hour: number;
  scheduled_minute: number;
  schedule_bucket: number;
  status: string;
  claimed_by?: string;
  claim_expires_at?: string;
};

export const runRetention = inngest.createFunction(
  { id: "run-retention" },
  { cron: "*/5 * * * *" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    const maxTenantsPerTick = Number.parseInt(process.env.SCHEDULE_MAX_TENANTS_PER_TICK ?? "10", 10);
    if (!baseUrl) {
      throw new Error("HARNESS_BASE_URL is required");
    }
    return step.run("run-tenant-retention", async () => {
      const evaluatedAt = new Date().toISOString();
      const dueTenantsResponse = await fetch(`${baseUrl}/schedules/claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_type: "retention",
          utc_iso: evaluatedAt,
          max_tenants: maxTenantsPerTick,
          claimer_id: "inngest/run-retention",
        }),
      });
      if (!dueTenantsResponse.ok) {
        throw new Error(`Due-tenant lookup failed with status ${dueTenantsResponse.status}`);
      }
      const dueTenants = (await dueTenantsResponse.json()) as DueTenant[];
      const runs = [];
      const failures = [];
      for (const tenant of dueTenants) {
        try {
          await fetch(`${baseUrl}/schedules/heartbeat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: tenant.id,
              actor_id: "inngest/run-retention",
              claim_ttl_seconds: 600,
            }),
          });
          const response = await fetch(`${baseUrl}/retention/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tenant_id: tenant.tenant_id, dry_run: false }),
          });
          if (!response.ok) {
            throw new Error(`Retention run failed for ${tenant.tenant_id} with status ${response.status}`);
          }
          const result = await response.json();
          await fetch(`${baseUrl}/schedules/finalize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: tenant.id,
              action: "complete",
              actor_id: "inngest/run-retention",
              note: "Retention run completed",
            }),
          });
          runs.push({
            tenant_id: tenant.tenant_id,
            tenant_slug: tenant.tenant_slug,
            timezone: tenant.timezone,
            scheduled_minute: tenant.scheduled_minute,
            result,
          });
        } catch (error) {
          await fetch(`${baseUrl}/schedules/finalize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: tenant.id,
              action: "release",
              actor_id: "inngest/run-retention",
              note: error instanceof Error ? error.message : "Retention run failed",
            }),
          });
          failures.push({
            tenant_id: tenant.tenant_id,
            tenant_slug: tenant.tenant_slug,
            error: error instanceof Error ? error.message : String(error),
          });
        }
      }
      if (failures.length > 0) {
        throw new Error(`Retention run failures: ${JSON.stringify(failures)}`);
      }
      return {
        evaluated_at: evaluatedAt,
        claimed_tenant_count: dueTenants.length,
        max_tenants_per_tick: maxTenantsPerTick,
        runs,
      };
    });
  },
);
