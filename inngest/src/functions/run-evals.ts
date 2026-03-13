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

export const runEvals = inngest.createFunction(
  { id: "run-evals" },
  { cron: "*/5 * * * *" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    const maxTenantsPerTick = Number.parseInt(process.env.SCHEDULE_MAX_TENANTS_PER_TICK ?? "10", 10);
    if (!baseUrl) {
      throw new Error("HARNESS_BASE_URL is required");
    }
    return step.run("run-evals", async () => {
      const evaluatedAt = new Date();
      const evaluatedAtIso = evaluatedAt.toISOString();
      const results = {
        evaluated_at: evaluatedAtIso,
        global_runs: [] as Array<{ level: "core" | "industry"; result: unknown }>,
        tenant_runs: [] as Array<{
          tenant_id: string;
          tenant_slug?: string;
          timezone: string;
          scheduled_minute: number;
          result: unknown;
        }>,
      };

      if (evaluatedAt.getUTCHours() === 4 && evaluatedAt.getUTCMinutes() === 0) {
        const levels = ["core", "industry"] as const;
        for (const level of levels) {
          const response = await fetch(`${baseUrl}/evals/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ level }),
          });
          if (!response.ok) {
            throw new Error(`Eval run for ${level} failed with status ${response.status}`);
          }
          results.global_runs.push({ level, result: await response.json() });
        }
      }

      const dueTenantsResponse = await fetch(`${baseUrl}/schedules/claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_type: "tenant_eval",
          utc_iso: evaluatedAtIso,
          max_tenants: maxTenantsPerTick,
          claimer_id: "inngest/run-evals",
        }),
      });
      if (!dueTenantsResponse.ok) {
        throw new Error(`Due-tenant lookup failed with status ${dueTenantsResponse.status}`);
      }
      const dueTenants = (await dueTenantsResponse.json()) as DueTenant[];
      const failures = [];
      for (const tenant of dueTenants) {
        try {
          await fetch(`${baseUrl}/schedules/heartbeat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: tenant.id,
              actor_id: "inngest/run-evals",
              claim_ttl_seconds: 600,
            }),
          });
          const response = await fetch(`${baseUrl}/evals/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ level: "tenant", tenant_id: tenant.tenant_id }),
          });
          if (!response.ok) {
            throw new Error(`Tenant eval run failed for ${tenant.tenant_id} with status ${response.status}`);
          }
          const result = await response.json();
          await fetch(`${baseUrl}/schedules/finalize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              entry_id: tenant.id,
              action: "complete",
              actor_id: "inngest/run-evals",
              note: "Tenant eval run completed",
            }),
          });
          results.tenant_runs.push({
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
              actor_id: "inngest/run-evals",
              note: error instanceof Error ? error.message : "Tenant eval run failed",
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
        throw new Error(`Tenant eval failures: ${JSON.stringify(failures)}`);
      }
      return results;
    });
  },
);
