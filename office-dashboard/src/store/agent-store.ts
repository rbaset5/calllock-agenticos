import { create } from "zustand";

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

export type AgentState = {
  department: string;
  role: string;
  current_state: string;
  description: string | null;
  supervisor_id?: string | null;
  call_id?: string | null;
  updated_at?: string | null;
};

export type AgentOfficeStateRow = {
  agent_id: string;
  tenant_id: string;
  department: string;
  role: string;
  supervisor_id: string | null;
  current_state: string;
  description: string | null;
  call_id: string | null;
  updated_at: string;
};

export type QuestOption = Record<string, unknown>;

export type QuestLogEntry = {
  id: string;
  tenant_id: string;
  agent_id: string;
  department: string;
  call_id: string | null;
  rule_violated: string;
  summary: string;
  options: QuestOption[];
  urgency: string;
  status: string;
  resolution: string | null;
  resolved_by: string | null;
  created_at: string;
  resolved_at: string | null;
};

type AgentStore = {
  agents: Map<string, AgentState>;
  quests: QuestLogEntry[];
  connectionStatus: ConnectionStatus;
  upsertAgent: (row: AgentOfficeStateRow) => void;
  removeAgent: (agentId: string) => void;
  upsertQuest: (quest: QuestLogEntry) => void;
  removeQuest: (questId: string) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  reset: () => void;
};

function sortQuests(quests: QuestLogEntry[]) {
  return [...quests].sort((left, right) =>
    right.created_at.localeCompare(left.created_at)
  );
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents: new Map<string, AgentState>(),
  quests: [],
  connectionStatus: "disconnected",
  upsertAgent: (row) =>
    set((state) => {
      const nextAgents = new Map(state.agents);
      nextAgents.set(row.agent_id, {
        department: row.department,
        role: row.role,
        current_state: row.current_state,
        description: row.description,
        supervisor_id: row.supervisor_id,
        call_id: row.call_id,
        updated_at: row.updated_at,
      });

      return { agents: nextAgents };
    }),
  removeAgent: (agentId) =>
    set((state) => {
      const nextAgents = new Map(state.agents);
      nextAgents.delete(agentId);
      return { agents: nextAgents };
    }),
  upsertQuest: (quest) =>
    set((state) => {
      const nextQuests = state.quests.filter((entry) => entry.id !== quest.id);
      nextQuests.push(quest);
      return { quests: sortQuests(nextQuests) };
    }),
  removeQuest: (questId) =>
    set((state) => ({
      quests: state.quests.filter((quest) => quest.id !== questId),
    })),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  reset: () =>
    set({
      agents: new Map<string, AgentState>(),
      quests: [],
      connectionStatus: "disconnected",
    }),
}));
