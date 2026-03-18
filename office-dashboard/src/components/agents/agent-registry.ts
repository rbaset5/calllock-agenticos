import {
  DEPARTMENT_ACCENT_COLORS,
  type AgentZoneKey,
  type DepartmentKey,
  type RoomKey,
} from "@/components/rooms/shared";

export type AgentRole = "executive" | "director" | "worker";

export type AgentRegistryEntry = {
  id: string;
  name: string;
  department: DepartmentKey;
  role: AgentRole;
  roomAssignment: RoomKey;
  accentColor: string;
  seatIndex: number;
};

const EXECUTIVE_ROOM = "executive_suite";
const PRODUCT_ROOM = "product_room";
const ENGINEERING_ROOM = "engineering_room";
const GROWTH_ROOM = "growth_marketing_room";
const CS_ROOM = "customer_success_room";
const FINANCE_ROOM = "finance_legal_room";
const LOBBY_ROOM = "central_lobby";

function buildAgent(
  id: string,
  name: string,
  department: DepartmentKey,
  role: AgentRole,
  roomAssignment: RoomKey,
  seatIndex: number
): AgentRegistryEntry {
  return {
    id,
    name,
    department,
    role,
    roomAssignment,
    accentColor: DEPARTMENT_ACCENT_COLORS[department],
    seatIndex,
  };
}

export const AGENT_ROSTER: AgentRegistryEntry[] = [
  buildAgent("exec-ceo", "CEO / Founder", "executive", "executive", EXECUTIVE_ROOM, 0),
  buildAgent("exec-cpo", "CPO", "executive", "executive", EXECUTIVE_ROOM, 1),
  buildAgent("exec-cto", "CTO", "executive", "executive", EXECUTIVE_ROOM, 2),
  buildAgent("exec-coo", "COO", "executive", "executive", EXECUTIVE_ROOM, 3),

  buildAgent("pm-product-strategy", "Head of Product", "product_mgmt", "director", PRODUCT_ROOM, 0),
  buildAgent("pm-product-discovery", "PM Discovery", "product_mgmt", "worker", PRODUCT_ROOM, 1),
  buildAgent("pm-execution", "PO Execution", "product_mgmt", "worker", PRODUCT_ROOM, 2),
  buildAgent("pm-market-research", "Market Researcher", "product_mgmt", "worker", PRODUCT_ROOM, 3),
  buildAgent("pm-data-analytics", "Product Data Analyst", "product_mgmt", "worker", PRODUCT_ROOM, 4),
  buildAgent("pm-toolkit", "ProdOps", "product_mgmt", "worker", PRODUCT_ROOM, 5),
  buildAgent("pm-designer", "Lead Designer", "product_mgmt", "worker", PRODUCT_ROOM, 6),

  buildAgent("eng-vp", "VP Engineering", "engineering", "director", ENGINEERING_ROOM, 0),
  buildAgent("eng-ai-voice", "AI/Voice Engineer", "engineering", "worker", ENGINEERING_ROOM, 1),
  buildAgent("eng-fullstack", "Full-Stack Dev", "engineering", "worker", ENGINEERING_ROOM, 2),
  buildAgent("eng-qa", "QA Engineer", "engineering", "worker", ENGINEERING_ROOM, 3),

  buildAgent("growth-head", "Head of Growth", "growth_marketing", "director", GROWTH_ROOM, 0),
  buildAgent("growth-cro", "CRO Specialist", "growth_marketing", "worker", GROWTH_ROOM, 1),
  buildAgent("growth-content", "Content & Copy", "growth_marketing", "worker", GROWTH_ROOM, 2),
  buildAgent("growth-engineer", "Growth Engineer", "growth_marketing", "worker", GROWTH_ROOM, 3),
  buildAgent("growth-lifecycle", "Lifecycle Marketer", "growth_marketing", "worker", GROWTH_ROOM, 4),
  buildAgent("growth-analyst", "Growth Analyst", "growth_marketing", "worker", GROWTH_ROOM, 5),

  buildAgent("sales-sdr", "SDR / Lead Router", "sales", "worker", LOBBY_ROOM, 0),

  buildAgent("cs-head", "Head of CS", "customer_success", "director", CS_ROOM, 0),
  buildAgent("cs-onboarding", "Onboarding Specialist", "customer_success", "worker", CS_ROOM, 1),
  buildAgent("cs-account-manager", "Account Manager", "customer_success", "worker", CS_ROOM, 2),
  buildAgent("cs-tech-support", "Pod Tech Support", "customer_success", "worker", CS_ROOM, 3),
  buildAgent("cs-associate", "Pod Success Associate", "customer_success", "worker", CS_ROOM, 4),

  buildAgent("fin-lead", "Finance Lead", "finance_legal", "director", FINANCE_ROOM, 0),
  buildAgent("fin-accounting", "Accounting", "finance_legal", "worker", FINANCE_ROOM, 1),
  buildAgent("fin-legal", "Legal / Compliance", "finance_legal", "worker", FINANCE_ROOM, 2),
];

export const AGENT_REGISTRY: Record<string, AgentRegistryEntry> = Object.fromEntries(
  AGENT_ROSTER.map((agent) => [agent.id, agent])
);

export function normalizeAgentStateToZone(state: string | null | undefined): AgentZoneKey {
  const normalized = (state ?? "").trim().toLowerCase();

  if (!normalized || normalized === "idle" || normalized === "queued") {
    return "idle";
  }
  if (normalized.includes("context")) {
    return "context_assembly";
  }
  if (
    normalized.includes("policy") ||
    normalized === "blocked" ||
    normalized.includes("approval")
  ) {
    return "policy_gate";
  }
  if (
    normalized === "worker" ||
    normalized.includes("execute") ||
    normalized.includes("working")
  ) {
    return "execution";
  }
  if (normalized.includes("verification") || normalized.includes("review")) {
    return "verification";
  }
  if (
    normalized.includes("persist") ||
    normalized.includes("dispatch") ||
    normalized.includes("complete") ||
    normalized.includes("done")
  ) {
    return "persistence";
  }
  if (normalized.includes("error") || normalized.includes("failed")) {
    return "error";
  }

  return "idle";
}
