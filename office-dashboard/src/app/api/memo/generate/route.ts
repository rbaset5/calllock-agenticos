import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

type GenerateMemoPayload = {
  date?: string;
  tenant_id?: string;
};

type QuestRow = {
  department: string;
};

type AgentRow = {
  department: string;
  current_state: string;
};

type MetricEventRow = {
  category: string;
  event_name: string;
  worker_id: string | null;
  dimensions: Record<string, unknown> | null;
};

type DepartmentSummary = {
  name: string;
  items: string[];
};

function getSupabaseAdminClient() {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    throw new Error(
      "SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY are required"
    );
  }

  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

function humanizeDepartment(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function incrementCount(
  counts: Record<string, number>,
  key: string,
  amount = 1
) {
  counts[key] = (counts[key] ?? 0) + amount;
}

function metricDepartment(metric: MetricEventRow) {
  const dimensionDepartment = metric.dimensions?.department;
  if (typeof dimensionDepartment === "string" && dimensionDepartment.length > 0) {
    return dimensionDepartment;
  }

  return "cross_team";
}

export async function POST(request: Request) {
  let payload: GenerateMemoPayload;

  try {
    payload = (await request.json()) as GenerateMemoPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload" }, { status: 400 });
  }

  const date = payload.date?.trim();
  const tenantId = payload.tenant_id?.trim();

  if (!date || !tenantId) {
    return NextResponse.json(
      { error: "date and tenant_id are required" },
      { status: 400 }
    );
  }

  const start = `${date}T00:00:00.000Z`;
  const end = `${date}T23:59:59.999Z`;

  try {
    const supabase = getSupabaseAdminClient();

    const [
      resolvedQuestResult,
      activeAgentResult,
      metricEventResult,
    ] = await Promise.all([
      supabase
        .from("quest_log")
        .select("department")
        .eq("tenant_id", tenantId)
        .eq("status", "resolved")
        .gte("resolved_at", start)
        .lte("resolved_at", end),
      supabase
        .from("agent_office_state")
        .select("department,current_state")
        .eq("tenant_id", tenantId)
        .gte("updated_at", start)
        .lte("updated_at", end),
      supabase
        .from("metric_events")
        .select("category,event_name,worker_id,dimensions")
        .eq("tenant_id", tenantId)
        .gte("created_at", start)
        .lte("created_at", end),
    ]);

    if (resolvedQuestResult.error) {
      throw resolvedQuestResult.error;
    }
    if (activeAgentResult.error) {
      throw activeAgentResult.error;
    }
    if (metricEventResult.error) {
      throw metricEventResult.error;
    }

    const resolvedCounts: Record<string, number> = {};
    for (const quest of (resolvedQuestResult.data ?? []) as QuestRow[]) {
      incrementCount(resolvedCounts, quest.department);
    }

    const activeCounts: Record<string, number> = {};
    for (const agent of (activeAgentResult.data ?? []) as AgentRow[]) {
      if (agent.current_state && agent.current_state !== "idle") {
        incrementCount(activeCounts, agent.department);
      }
    }

    const metricCounts: Record<string, number> = {};
    const metricHighlights: Record<string, Record<string, number>> = {};
    for (const metric of (metricEventResult.data ?? []) as MetricEventRow[]) {
      const department = metricDepartment(metric);
      incrementCount(metricCounts, department);

      const label = `${metric.category}:${metric.event_name}`;
      if (!metricHighlights[department]) {
        metricHighlights[department] = {};
      }
      incrementCount(metricHighlights[department], label);
    }

    const departmentKeys = Array.from(
      new Set([
        ...Object.keys(resolvedCounts),
        ...Object.keys(activeCounts),
        ...Object.keys(metricCounts),
      ])
    );

    const preferredOrder = [
      "executive",
      "product_mgmt",
      "engineering",
      "growth_marketing",
      "sales",
      "customer_success",
      "finance_legal",
      "cross_team",
    ];

    departmentKeys.sort((left, right) => {
      return preferredOrder.indexOf(left) - preferredOrder.indexOf(right);
    });

    const departments: DepartmentSummary[] = departmentKeys.map((department) => {
      const items: string[] = [];
      const resolvedCount = resolvedCounts[department] ?? 0;
      const activeCount = activeCounts[department] ?? 0;
      const metricsCount = metricCounts[department] ?? 0;

      if (resolvedCount > 0) {
        items.push(`Resolved ${resolvedCount} quest${resolvedCount === 1 ? "" : "s"}.`);
      }

      if (activeCount > 0) {
        items.push(`Observed ${activeCount} active agent${activeCount === 1 ? "" : "s"} in the office snapshot.`);
      }

      if (metricsCount > 0) {
        const topMetrics = Object.entries(metricHighlights[department] ?? {})
          .sort((left, right) => right[1] - left[1])
          .slice(0, 2)
          .map(([label, count]) => `${count} ${label}`)
          .join(", ");

        items.push(
          topMetrics.length > 0
            ? `Recorded ${metricsCount} metric event${metricsCount === 1 ? "" : "s"} (${topMetrics}).`
            : `Recorded ${metricsCount} metric event${metricsCount === 1 ? "" : "s"}.`
        );
      }

      if (items.length === 0) {
        items.push("No notable activity captured for this date.");
      }

      return {
        name: department === "cross_team" ? "Cross-Team" : humanizeDepartment(department),
        items,
      };
    });

    const content = { departments };

    const { data, error } = await supabase
      .from("daily_memo")
      .upsert(
        {
          tenant_id: tenantId,
          memo_date: date,
          content,
          generated_at: new Date().toISOString(),
        },
        { onConflict: "tenant_id,memo_date" }
      )
      .select("*")
      .single();

    if (error) {
      throw error;
    }

    return NextResponse.json({ memo: data }, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : "Failed to generate memo",
      },
      { status: 500 }
    );
  }
}
