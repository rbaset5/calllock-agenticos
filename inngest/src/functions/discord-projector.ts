import { inngest } from "../inngest.js";

const DISCORD_WEBHOOK_URL = process.env.DISCORD_WEBHOOK_URL || "";

interface DiscordEmbed {
  title: string;
  description: string;
  color: number;
  timestamp?: string;
  fields?: Array<{ name: string; value: string; inline?: boolean }>;
}

const GREEN = 0x22c55e;
const YELLOW = 0xeab308;
const RED = 0xef4444;

function statusColor(status: string): number {
  if (status === "pass" || status === "green" || status === "started") return GREEN;
  if (status === "warning" || status === "yellow" || status === "pending") return YELLOW;
  return RED;
}

async function postToDiscord(embed: DiscordEmbed): Promise<void> {
  if (!DISCORD_WEBHOOK_URL) return;

  await fetch(DISCORD_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ embeds: [embed] }),
  });
}

export const discordAgentState = inngest.createFunction(
  { id: "discord-agent-state", name: "Discord: Agent State Change" },
  { event: "calllock/agent.state.changed" },
  async ({ event }: { event: { data: Record<string, unknown> } }) => {
    const { agent_id, department, to_state, task_type } = event.data;
    await postToDiscord({
      title: `${String(agent_id ?? "unknown")} → ${String(to_state ?? "unknown")}`,
      description: `Department: ${String(department ?? "unknown")}\nTask: ${String(task_type ?? "general")}`,
      color: statusColor(String(to_state ?? "unknown")),
      timestamp: new Date().toISOString(),
    });
  },
);

export const discordVerification = inngest.createFunction(
  { id: "discord-verification", name: "Discord: Verification Result" },
  { event: "calllock/agent.verification" },
  async ({ event }: { event: { data: Record<string, unknown> } }) => {
    const { worker_id, outcome, confidence, task_type } = event.data;
    const confidenceNumber = typeof confidence === "number" ? confidence : 0;
    await postToDiscord({
      title: `Verification: ${String(worker_id ?? "unknown")} — ${String(outcome ?? "unknown")}`,
      description: `Confidence: ${(confidenceNumber * 100).toFixed(1)}%\nTask: ${String(task_type ?? "")}`,
      color: statusColor(String(outcome ?? "unknown")),
      timestamp: new Date().toISOString(),
      fields: [
        { name: "Worker", value: String(worker_id ?? "unknown"), inline: true },
        { name: "Outcome", value: String(outcome ?? "unknown"), inline: true },
      ],
    });
  },
);

export const discordSkillCandidate = inngest.createFunction(
  { id: "discord-skill-candidate", name: "Discord: Skill Candidate" },
  { event: "calllock/skill.candidate" },
  async ({ event }: { event: { data: Record<string, unknown> } }) => {
    const { worker_id, signals, summary } = event.data;
    const signalList = Array.isArray(signals) ? signals.map((signal) => String(signal)) : [];
    await postToDiscord({
      title: `Skill Candidate: ${String(worker_id ?? "unknown")}`,
      description: String(summary ?? "New skill candidate detected"),
      color: YELLOW,
      timestamp: new Date().toISOString(),
      fields: [
        { name: "Signals", value: signalList.join(", "), inline: false },
      ],
    });
  },
);

export const discordHealthCheck = inngest.createFunction(
  { id: "discord-health-check", name: "Discord: Health Check" },
  { event: "calllock/guardian.health" },
  async ({ event }: { event: { data: Record<string, unknown> } }) => {
    const { agent_id, status, summary } = event.data;
    await postToDiscord({
      title: `Health Check: ${String(agent_id ?? "unknown")} — ${String(status ?? "unknown")}`,
      description: String(summary ?? ""),
      color: statusColor(String(status ?? "unknown")),
      timestamp: new Date().toISOString(),
    });
  },
);
