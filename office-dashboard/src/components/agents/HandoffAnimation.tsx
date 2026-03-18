"use client";

import { Outlines } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { Group, Vector3 } from "three";

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

const SEGMENT_DURATIONS = [0.5, 1.5, 0.5] as const;
const TOTAL_DURATION = SEGMENT_DURATIONS[0] + SEGMENT_DURATIONS[1] + SEGMENT_DURATIONS[2];
const LOBBY_HUB: Vec3 = [0, 0.52, 0.4];
const BRIEFCASE_OFFSET: Vec3 = [0.28, 0.72, 0];

const ROOM_EXIT_POSITIONS: Record<RoomKey, Vec3> = {
  executive_suite: [0, 0.92, 9.2],
  product_room: [-15, 0.52, 13.6],
  finance_legal_room: [15, 0.52, 13],
  central_lobby: [0, 0.52, 4.8],
  engineering_room: [-15, 0.52, -6.4],
  growth_marketing_room: [0, 0.52, -9.7],
  customer_success_room: [15, 0.52, -6.8],
};

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

function addVectors(...vectors: Vec3[]): Vec3 {
  return vectors.reduce<Vec3>(
    (acc, [x, y, z]) => [acc[0] + x, acc[1] + y, acc[2] + z],
    [0, 0, 0]
  );
}

function getSeatOffset(roomKey: RoomKey, seatIndex: number): Vec3 {
  const offsets = roomKey === "central_lobby" ? LOBBY_SEAT_OFFSETS : SEAT_OFFSETS;
  return offsets[seatIndex % offsets.length];
}

function getAgentAnchor(agentId: string, currentState: string | undefined | null): Vec3 | null {
  const registry = AGENT_REGISTRY[agentId];
  if (!registry) {
    return null;
  }

  const roomOrigin = ROOM_POSITIONS[registry.roomAssignment];
  const zoneKey = normalizeAgentStateToZone(currentState);
  const zoneOrigin = ROOM_ZONE_POSITIONS[registry.roomAssignment][zoneKey];
  const seatOffset = getSeatOffset(registry.roomAssignment, registry.seatIndex);

  return addVectors(roomOrigin, zoneOrigin, seatOffset);
}

function getDestinationContextAnchor(agentId: string): Vec3 | null {
  const registry = AGENT_REGISTRY[agentId];
  if (!registry) {
    return null;
  }

  const roomOrigin = ROOM_POSITIONS[registry.roomAssignment];
  const zoneOrigin = ROOM_ZONE_POSITIONS[registry.roomAssignment].context_assembly;
  const seatOffset = getSeatOffset(registry.roomAssignment, registry.seatIndex);
  return addVectors(roomOrigin, zoneOrigin, seatOffset);
}

function useAnimationPath(
  fromAgentId: string,
  toAgentId: string,
  sourceState: string | null | undefined
) {
  return useMemo(() => {
    const sourceRegistry = AGENT_REGISTRY[fromAgentId];
    const destinationRegistry = AGENT_REGISTRY[toAgentId];
    if (!sourceRegistry || !destinationRegistry) {
      return null;
    }

    const start = getAgentAnchor(fromAgentId, sourceState);
    const roomExit = ROOM_EXIT_POSITIONS[sourceRegistry.roomAssignment];
    const destinationExit = ROOM_EXIT_POSITIONS[destinationRegistry.roomAssignment];
    const destination = getDestinationContextAnchor(toAgentId);

    if (!start || !destination) {
      return null;
    }

    return [start, roomExit, LOBBY_HUB, destinationExit, destination] as const;
  }, [fromAgentId, toAgentId, sourceState]);
}

function HandoffCourier({
  handoffId,
  fromAgentId,
  toAgentId,
  sourceState,
  summary,
  onComplete,
}: {
  handoffId: string;
  fromAgentId: string;
  toAgentId: string;
  sourceState: string | null | undefined;
  summary: string;
  onComplete: (handoffId: string) => void;
}) {
  const path = useAnimationPath(fromAgentId, toAgentId, sourceState);
  const sourceRegistry = AGENT_REGISTRY[fromAgentId];
  const groupRef = useRef<Group>(null);
  const targetRef = useRef(new Vector3());
  const completedRef = useRef(false);
  const elapsedRef = useRef(0);

  useEffect(() => {
    elapsedRef.current = 0;
    completedRef.current = false;
  }, [handoffId]);

  useFrame((_, delta) => {
    const group = groupRef.current;
    if (!group || !path || !sourceRegistry) {
      return;
    }

    elapsedRef.current += delta;
    const elapsed = elapsedRef.current;

    let from: Vec3;
    let to: Vec3;
    let t: number;

    if (elapsed <= SEGMENT_DURATIONS[0]) {
      from = path[0];
      to = path[1];
      t = elapsed / SEGMENT_DURATIONS[0];
    } else if (elapsed <= SEGMENT_DURATIONS[0] + SEGMENT_DURATIONS[1]) {
      from = path[1];
      to = path[3];
      t = (elapsed - SEGMENT_DURATIONS[0]) / SEGMENT_DURATIONS[1];
    } else {
      from = path[3];
      to = path[4];
      t = Math.min(
        1,
        (elapsed - SEGMENT_DURATIONS[0] - SEGMENT_DURATIONS[1]) /
          SEGMENT_DURATIONS[2]
      );
    }

    targetRef.current.set(
      from[0] + (to[0] - from[0]) * t,
      from[1] + Math.sin(elapsed * 7) * 0.06,
      from[2] + (to[2] - from[2]) * t
    );
    group.position.lerp(targetRef.current, 1 - Math.exp(-delta * 10));

    if (!completedRef.current && elapsed >= TOTAL_DURATION) {
      completedRef.current = true;
      onComplete(handoffId);
    }
  });

  if (!path || !sourceRegistry) {
    return null;
  }

  const accentColor = sourceRegistry.accentColor;
  const headColor = `${accentColor}CC`;

  return (
    <group ref={groupRef} position={path[0]}>
      <mesh castShadow receiveShadow position={[0, 0.62, 0]}>
        <cylinderGeometry args={[0.24, 0.32, 0.82, 6]} />
        <meshToonMaterial color={accentColor} />
        <Outlines thickness={0.03} color="#0f172a" />
      </mesh>

      <mesh castShadow receiveShadow position={[0, 1.25, 0]}>
        <sphereGeometry args={[0.26, 8, 8]} />
        <meshToonMaterial color={headColor} />
        <Outlines thickness={0.025} color="#0f172a" />
      </mesh>

      <mesh castShadow receiveShadow position={BRIEFCASE_OFFSET}>
        <boxGeometry args={[0.22, 0.18, 0.16]} />
        <meshStandardMaterial
          color="#60a5fa"
          emissive="#60a5fa"
          emissiveIntensity={1.25}
        />
        <Outlines thickness={0.02} color="#0f172a" />
      </mesh>

      <mesh castShadow receiveShadow position={[0.18, 0.72, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 0.28, 6]} />
        <meshToonMaterial color="#334155" />
        <Outlines thickness={0.015} color="#0f172a" />
      </mesh>

      <mesh castShadow receiveShadow position={[-0.18, 0.2, 0]}>
        <cylinderGeometry args={[0.06, 0.06, 0.36, 6]} />
        <meshToonMaterial color="#334155" />
        <Outlines thickness={0.02} color="#0f172a" />
      </mesh>

      <mesh castShadow receiveShadow position={[0.18, 0.2, 0]}>
        <cylinderGeometry args={[0.06, 0.06, 0.36, 6]} />
        <meshToonMaterial color="#334155" />
        <Outlines thickness={0.02} color="#0f172a" />
      </mesh>

      <mesh position={[0, 1.72, 0]}>
        <sphereGeometry args={[0.08, 8, 8]} />
        <meshStandardMaterial
          color="#e0f2fe"
          emissive="#7dd3fc"
          emissiveIntensity={0.9}
          transparent
          opacity={0.65}
        />
      </mesh>

      <group position={[0, 1.78, 0]}>
        <mesh>
          <planeGeometry args={[Math.min(1.8, Math.max(0.7, summary.length * 0.03)), 0.22]} />
          <meshBasicMaterial color="#020617" transparent opacity={0.45} />
        </mesh>
      </group>
    </group>
  );
}

export default function HandoffAnimation() {
  const handoffs = useAgentStore((state) => state.handoffs);
  const agents = useAgentStore((state) => state.agents);
  const removeHandoff = useAgentStore((state) => state.removeHandoff);

  return (
    <group>
      {handoffs.map((handoff) => (
        <HandoffCourier
          key={handoff.id}
          handoffId={handoff.id}
          fromAgentId={handoff.from_agent_id}
          toAgentId={handoff.to_agent_id}
          sourceState={agents.get(handoff.from_agent_id)?.current_state}
          summary={handoff.context_summary ?? handoff.context_type}
          onComplete={removeHandoff}
        />
      ))}
    </group>
  );
}
