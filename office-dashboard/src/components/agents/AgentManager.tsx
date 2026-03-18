"use client";

import AgentCharacter from "./AgentCharacter";
import {
  AGENT_REGISTRY,
  normalizeAgentStateToZone,
} from "./agent-registry";
import {
  ROOM_POSITIONS,
  ROOM_ZONE_POSITIONS,
  type RoomKey,
  type Vec3,
} from "@/components/rooms/shared";
import { useAgentStore } from "@/store/agent-store";

const SEAT_OFFSETS: Vec3[] = [
  [0, 0, 0],
  [-0.36, 0, -0.24],
  [0.36, 0, -0.24],
  [-0.36, 0, 0.24],
  [0.36, 0, 0.24],
  [0, 0, -0.42],
  [0, 0, 0.42],
  [-0.54, 0, 0],
];

const LOBBY_SEAT_OFFSETS: Vec3[] = [
  [0, 0, 0],
  [0.26, 0, 0.18],
];

function getSeatOffset(roomKey: RoomKey, seatIndex: number): Vec3 {
  const offsets = roomKey === "central_lobby" ? LOBBY_SEAT_OFFSETS : SEAT_OFFSETS;
  return offsets[seatIndex % offsets.length];
}

function addVectors(left: Vec3, middle: Vec3, right: Vec3): Vec3 {
  return [
    left[0] + middle[0] + right[0],
    left[1] + middle[1] + right[1],
    left[2] + middle[2] + right[2],
  ];
}

export default function AgentManager() {
  const agents = useAgentStore((state) => state.agents);

  return (
    <group>
      {Array.from(agents.entries()).map(([agentId, runtimeState]) => {
        const agent = AGENT_REGISTRY[agentId];
        if (!agent) {
          return null;
        }

        const zoneKey = normalizeAgentStateToZone(runtimeState.current_state);
        const roomOrigin = ROOM_POSITIONS[agent.roomAssignment];
        const zoneOrigin = ROOM_ZONE_POSITIONS[agent.roomAssignment][zoneKey];
        const seatOffset = getSeatOffset(agent.roomAssignment, agent.seatIndex);
        const targetPosition = addVectors(roomOrigin, zoneOrigin, seatOffset);

        return (
          <AgentCharacter
            key={agentId}
            name={agent.name}
            accentColor={agent.accentColor}
            targetPosition={targetPosition}
            taskDescription={runtimeState.description ?? runtimeState.current_state ?? agent.role}
          />
        );
      })}
    </group>
  );
}
