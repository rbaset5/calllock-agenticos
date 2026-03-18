import { inngest } from "../inngest.js";

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

/**
 * Watchdog cron: fires at 7:30 AM daily, after all three guardian
 * agents should have reported. Checks agent_reports and alerts if any
 * report is missing.
 */
export const guardianWatchdog = inngest.createFunction(
  {
    id: "guardian-watchdog",
    name: "Guardian Self-Monitoring Watchdog",
  },
  { cron: "30 7 * * *" },
  async ({ step }: any) => {
    const today = new Date().toISOString().split("T")[0];
    const tenantId = process.env.DEFAULT_TENANT_ID;

    if (!tenantId) {
      return step.run("skip-watchdog", async () => ({
        skipped: true,
        reason: "DEFAULT_TENANT_ID not configured",
        date: today,
      }));
    }

    const { supabaseUrl, serviceRoleKey } = getSupabaseConfig();

    const missing = await step.run("check-reports", async () => {
      const expected = [
        { agent_id: "eng-ai-voice", expected_by: "6:15 AM" },
        { agent_id: "eng-app", expected_by: "6:45 AM" },
        { agent_id: "eng-product-qa", expected_by: "7:15 AM" },
      ];

      const response = await fetch(
        `${supabaseUrl}/rest/v1/agent_reports?tenant_id=eq.${tenantId}&report_date=eq.${today}&select=agent_id`,
        {
          headers: {
            apikey: serviceRoleKey,
            Authorization: `Bearer ${serviceRoleKey}`,
          },
        },
      );

      if (!response.ok) {
        throw new Error(`Agent report lookup failed with status ${response.status}`);
      }

      const reports = (await response.json()) as Array<{ agent_id: string }>;
      const reportedAgents = new Set(reports.map((row) => row.agent_id));

      return expected.filter((entry) => !reportedAgents.has(entry.agent_id)).map((entry) => ({ ...entry, date: today }));
    });

    if (missing.length > 0) {
      await step.run("alert-missing", async () => {
        const slackUrl = process.env.SLACK_WEBHOOK_URL;
        if (!slackUrl) {
          return { skipped: true, reason: "no SLACK_WEBHOOK_URL" };
        }

        const agentList = missing
          .map((entry: { agent_id: string; expected_by: string }) => `• *${entry.agent_id}* (expected by ${entry.expected_by})`)
          .join("\n");

        const response = await fetch(slackUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: `Guardian watchdog: ${missing.length} agent(s) did not report today (${today}):\n${agentList}`,
          }),
        });

        if (!response.ok) {
          throw new Error(`Slack webhook failed with status ${response.status}`);
        }

        return { alerted: true, missing_count: missing.length };
      });

      await step.run("create-quest", async () => {
        for (const entry of missing) {
          const response = await fetch(`${supabaseUrl}/rest/v1/quest_log`, {
            method: "POST",
            headers: {
              apikey: serviceRoleKey,
              Authorization: `Bearer ${serviceRoleKey}`,
              "Content-Type": "application/json",
              Prefer: "return=minimal",
            },
            body: JSON.stringify({
              tenant_id: tenantId,
              agent_id: entry.agent_id,
              department: "engineering",
              rule_violated: "guardian-agent-missing-report",
              summary: `Guardian agent ${entry.agent_id} did not report today (expected by ${entry.expected_by})`,
              urgency: "high",
              status: "pending",
            }),
          });

          if (!response.ok) {
            throw new Error(`Quest creation failed with status ${response.status}`);
          }
        }

        return { quests_created: missing.length };
      });
    }

    return { date: today, tenant_id: tenantId, missing_count: missing.length, missing };
  },
);
