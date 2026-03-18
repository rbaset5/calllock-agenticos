"use client";

import { Outlines, Text } from "@react-three/drei";

export type Vec3 = [number, number, number];
export type DepartmentKey =
  | "executive"
  | "product_mgmt"
  | "engineering"
  | "growth_marketing"
  | "sales"
  | "customer_success"
  | "finance_legal";
export type RoomKey =
  | "executive_suite"
  | "product_room"
  | "engineering_room"
  | "growth_marketing_room"
  | "customer_success_room"
  | "finance_legal_room"
  | "central_lobby";
export type AgentZoneKey =
  | "idle"
  | "context_assembly"
  | "policy_gate"
  | "execution"
  | "verification"
  | "persistence"
  | "error";

export type RoomComponentProps = {
  position?: Vec3;
};

type DepartmentRoomProps = RoomComponentProps & {
  name: string;
  accentColor: string;
  wallColor: string;
  size: [number, number];
  deskCount: number;
  elevated?: boolean;
  executiveStyle?: boolean;
};

type CorridorProps = {
  position: Vec3;
  size: [number, number, number];
};

const WALL_HEIGHT = 3.2;
const WALL_THICKNESS = 0.28;
const GLASS_HEIGHT = 2.5;
const GRID_COLOR = "#cbd5e1";
const OUTLINE_COLOR = "#111827";

export const DEPARTMENT_ACCENT_COLORS: Record<DepartmentKey, string> = {
  executive: "#D4A43A",
  product_mgmt: "#3B82F6",
  engineering: "#10B981",
  growth_marketing: "#8B5CF6",
  sales: "#EC4899",
  customer_success: "#F59E0B",
  finance_legal: "#6B7280",
};

export const ROOM_POSITIONS: Record<RoomKey, Vec3> = {
  executive_suite: [0, 0.4, 14],
  product_room: [-15, 0, 10],
  finance_legal_room: [15, 0, 10],
  central_lobby: [0, 0, 0],
  engineering_room: [-15, 0, -10.5],
  growth_marketing_room: [0, 0, -14],
  customer_success_room: [15, 0, -10.5],
};

function createDepartmentZonePositions(roomWidth: number, roomDepth: number) {
  return {
    idle: [-roomWidth * 0.28, 0.52, roomDepth * 0.2] as Vec3,
    context_assembly: [-roomWidth * 0.28, 0.52, -roomDepth * 0.14] as Vec3,
    policy_gate: [0, 0.52, roomDepth * 0.26] as Vec3,
    execution: [0, 0.52, -0.1] as Vec3,
    verification: [roomWidth * 0.24, 0.52, -0.08] as Vec3,
    persistence: [roomWidth * 0.28, 0.52, -roomDepth * 0.24] as Vec3,
    error: [roomWidth * 0.28, 0.52, roomDepth * 0.22] as Vec3,
  } satisfies Record<AgentZoneKey, Vec3>;
}

export const ROOM_ZONE_POSITIONS: Record<RoomKey, Record<AgentZoneKey, Vec3>> = {
  executive_suite: createDepartmentZonePositions(14, 10),
  product_room: createDepartmentZonePositions(11.5, 8.5),
  engineering_room: createDepartmentZonePositions(10.5, 8),
  growth_marketing_room: createDepartmentZonePositions(12.5, 8.5),
  customer_success_room: createDepartmentZonePositions(11.5, 8.2),
  finance_legal_room: createDepartmentZonePositions(9.8, 7.5),
  central_lobby: {
    idle: [-4.2, 0.52, 2.5],
    context_assembly: [4.3, 0.52, 2.5],
    policy_gate: [0, 0.52, 3.2],
    execution: [0, 0.52, -0.3],
    verification: [-2.8, 0.52, -0.6],
    persistence: [2.8, 0.52, -0.6],
    error: [0, 0.52, -3.1],
  },
};

function ToonBox({
  position = [0, 0, 0],
  size,
  color,
  rotation,
}: {
  position?: Vec3;
  size: [number, number, number];
  color: string;
  rotation?: Vec3;
}) {
  return (
    <mesh castShadow receiveShadow position={position} rotation={rotation}>
      <boxGeometry args={size} />
      <meshToonMaterial color={color} />
      <Outlines thickness={0.035} color={OUTLINE_COLOR} />
    </mesh>
  );
}

function GlassBox({
  position = [0, 0, 0],
  size,
}: {
  position?: Vec3;
  size: [number, number, number];
}) {
  return (
    <mesh position={position}>
      <boxGeometry args={size} />
      <meshPhysicalMaterial
        color="#dbeafe"
        transparent
        opacity={0.3}
        roughness={0.08}
        metalness={0}
      />
      <Outlines thickness={0.02} color="#bfdbfe" />
    </mesh>
  );
}

function FloorMarker({
  position,
  size,
  color,
  label,
}: {
  position: Vec3;
  size: [number, number];
  color: string;
  label: string;
}) {
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <planeGeometry args={size} />
        <meshStandardMaterial color={color} transparent opacity={0.18} />
      </mesh>
      <Text
        position={[0, 0.08, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.22}
        color="#e2e8f0"
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}

function CouchZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.4, 1.7]} color="#38bdf8" label="Idle" />
      <ToonBox position={[0, 0.27, 0.25]} size={[1.3, 0.45, 0.55]} color="#64748b" />
      <ToonBox position={[-0.46, 0.47, 0.25]} size={[0.22, 0.35, 0.55]} color="#475569" />
      <ToonBox position={[0.46, 0.47, 0.25]} size={[0.22, 0.35, 0.55]} color="#475569" />
      <ToonBox position={[0, 0.16, -0.35]} size={[0.5, 0.18, 0.5]} color="#cbd5e1" />
    </group>
  );
}

function ContextAssemblyZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.2, 1.8]} color="#22c55e" label="Context" />
      <ToonBox position={[-0.45, 0.55, 0.2]} size={[0.34, 1.1, 0.2]} color="#7c3f00" />
      <ToonBox position={[-0.45, 0.28, 0.2]} size={[0.42, 0.08, 0.26]} color="#f59e0b" />
      <ToonBox position={[0.35, 0.38, -0.05]} size={[0.9, 0.08, 0.55]} color="#eab308" />
      <ToonBox position={[0.35, 0.2, 0.12]} size={[0.08, 0.35, 0.08]} color="#94a3b8" />
      <ToonBox position={[0.68, 0.32, -0.18]} size={[0.28, 0.35, 0.28]} color="#94a3b8" />
    </group>
  );
}

function PolicyGateZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.1, 1.4]} color="#facc15" label="Policy Gate" />
      <ToonBox position={[-0.46, 0.45, 0]} size={[0.22, 0.9, 0.45]} color="#475569" />
      <ToonBox position={[0.46, 0.45, 0]} size={[0.22, 0.9, 0.45]} color="#475569" />
      <ToonBox position={[0, 0.58, 0]} size={[1.1, 0.08, 0.16]} color="#f59e0b" />
      <ToonBox position={[0, 0.24, 0.28]} size={[0.9, 0.12, 0.12]} color="#fbbf24" />
    </group>
  );
}

function ExecutionZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.3, 1.9]} color="#34d399" label="Execution" />
      <ToonBox position={[0, 0.58, 0.05]} size={[1.1, 0.1, 0.68]} color="#0f766e" />
      <ToonBox position={[-0.3, 0.92, -0.15]} size={[0.3, 0.28, 0.08]} color="#93c5fd" />
      <ToonBox position={[0.08, 0.92, -0.15]} size={[0.3, 0.28, 0.08]} color="#93c5fd" />
      <ToonBox position={[0.46, 0.92, -0.15]} size={[0.3, 0.28, 0.08]} color="#93c5fd" />
      <ToonBox position={[-0.45, 0.29, 0.08]} size={[0.1, 0.56, 0.1]} color="#475569" />
      <ToonBox position={[0.45, 0.29, 0.08]} size={[0.1, 0.56, 0.1]} color="#475569" />
    </group>
  );
}

function VerificationZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.1, 1.6]} color="#a78bfa" label="Verification" />
      <ToonBox position={[0, 0.36, 0]} size={[1.05, 0.14, 0.55]} color="#94a3b8" />
      <mesh position={[0.4, 0.62, -0.08]} rotation={[0, 0, Math.PI / 6]}>
        <cylinderGeometry args={[0.08, 0.08, 0.48, 12]} />
        <meshToonMaterial color="#e2e8f0" />
        <Outlines thickness={0.025} color={OUTLINE_COLOR} />
      </mesh>
      <mesh position={[0.58, 0.9, -0.16]}>
        <cylinderGeometry args={[0.16, 0.16, 0.06, 18]} />
        <meshToonMaterial color="#cbd5e1" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>
    </group>
  );
}

function PersistenceZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.1, 1.7]} color="#f59e0b" label="Persistence" />
      <ToonBox position={[-0.25, 0.55, 0]} size={[0.44, 1.1, 0.54]} color="#94a3b8" />
      <ToonBox position={[0.28, 0.55, 0]} size={[0.44, 1.1, 0.54]} color="#94a3b8" />
      <ToonBox position={[0, 0.12, -0.4]} size={[1.05, 0.24, 0.18]} color="#475569" />
    </group>
  );
}

function ErrorZone({ position }: { position: Vec3 }) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.2, 1.7]} color="#ef4444" label="Error" />
      <ToonBox position={[-0.26, 0.7, 0]} size={[0.38, 1.4, 0.38]} color="#1e293b" />
      <ToonBox position={[0.26, 0.7, 0]} size={[0.38, 1.4, 0.38]} color="#1e293b" />
      <mesh position={[0.1, 1.48, 0.12]}>
        <cylinderGeometry args={[0.05, 0.05, 0.2, 10]} />
        <meshToonMaterial color="#fb7185" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>
    </group>
  );
}

function DirectorCornerOffice({
  roomWidth,
  roomDepth,
  accentColor,
}: {
  roomWidth: number;
  roomDepth: number;
  accentColor: string;
}) {
  const offsetX = roomWidth / 2 - 1.55;
  const offsetZ = -roomDepth / 2 + 1.25;

  return (
    <group position={[offsetX, 0, offsetZ]}>
      <GlassBox position={[-0.65, 1.05, 0]} size={[0.08, 2.1, 2.3]} />
      <GlassBox position={[0, 1.05, 1.1]} size={[1.35, 2.1, 0.08]} />
      <ToonBox position={[0, 0.62, 0.25]} size={[1.15, 0.12, 0.58]} color={accentColor} />
      <ToonBox position={[0, 0.3, 0.22]} size={[0.12, 0.58, 0.12]} color="#475569" />
      <ToonBox position={[0.42, 0.88, 0.02]} size={[0.36, 0.25, 0.08]} color="#bfdbfe" />
      <Text
        position={[0, 0.08, 0.95]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.2}
        color="#f8fafc"
        anchorX="center"
      >
        Director
      </Text>
    </group>
  );
}

function WorkerDesks({
  count,
  roomWidth,
  roomDepth,
  accentColor,
  executiveStyle = false,
}: {
  count: number;
  roomWidth: number;
  roomDepth: number;
  accentColor: string;
  executiveStyle?: boolean;
}) {
  const columns = executiveStyle ? 2 : Math.min(3, Math.max(2, Math.ceil(count / 2)));
  const rows = Math.ceil(count / columns);
  const xStart = -((columns - 1) * 1.65) / 2;
  const zStart = executiveStyle ? -0.85 : -roomDepth / 2 + 2.1;

  return (
    <group>
      {Array.from({ length: count }, (_, index) => {
        const col = index % columns;
        const row = Math.floor(index / columns);
        const position: Vec3 = [
          xStart + col * 1.65,
          0,
          zStart + row * 1.75,
        ];

        return (
          <group key={`desk-${index}`} position={position}>
            <ToonBox position={[0, 0.48, 0]} size={[1.1, 0.1, 0.62]} color="#334155" />
            <ToonBox position={[0, 0.25, 0]} size={[0.1, 0.48, 0.1]} color="#475569" />
            <ToonBox position={[0, 0.82, -0.15]} size={[0.34, 0.22, 0.08]} color="#bae6fd" />
            <mesh position={[0.4, 0.24, 0.18]}>
              <cylinderGeometry args={[0.15, 0.15, 0.42, 12]} />
              <meshToonMaterial color={accentColor} />
              <Outlines thickness={0.02} color={OUTLINE_COLOR} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

export function DepartmentRoom({
  position = [0, 0, 0],
  name,
  accentColor,
  wallColor,
  size,
  deskCount,
  elevated = false,
  executiveStyle = false,
}: DepartmentRoomProps) {
  const [roomWidth, roomDepth] = size;
  const floorY = elevated ? 0.4 : 0;
  const wallY = floorY + WALL_HEIGHT / 2;
  const glassY = floorY + GLASS_HEIGHT / 2;

  return (
    <group position={position}>
      <ToonBox
        position={[0, floorY - 0.12, 0]}
        size={[roomWidth + 0.6, 0.24, roomDepth + 0.6]}
        color="#1e293b"
      />
      <mesh
        receiveShadow
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, floorY, 0]}
      >
        <planeGeometry args={[roomWidth, roomDepth]} />
        <meshToonMaterial color="#e2e8f0" />
      </mesh>
      <gridHelper
        args={[Math.max(roomWidth, roomDepth), Math.max(8, Math.round(Math.max(roomWidth, roomDepth) * 1.5)), GRID_COLOR, GRID_COLOR]}
        position={[0, floorY + 0.02, 0]}
      />

      <ToonBox
        position={[0, wallY, -roomDepth / 2 + WALL_THICKNESS / 2]}
        size={[roomWidth, WALL_HEIGHT, WALL_THICKNESS]}
        color={wallColor}
      />
      <ToonBox
        position={[-roomWidth / 2 + WALL_THICKNESS / 2, wallY, 0]}
        size={[WALL_THICKNESS, WALL_HEIGHT, roomDepth]}
        color={wallColor}
      />
      <ToonBox
        position={[roomWidth / 2 - WALL_THICKNESS / 2, wallY, 0]}
        size={[WALL_THICKNESS, WALL_HEIGHT, roomDepth]}
        color={wallColor}
      />
      <GlassBox
        position={[0, glassY, roomDepth / 2 - WALL_THICKNESS / 2]}
        size={[roomWidth, GLASS_HEIGHT, WALL_THICKNESS]}
      />
      <ToonBox
        position={[0, floorY + 0.02, -roomDepth / 2 + 0.3]}
        size={[roomWidth - 0.8, 0.04, 0.18]}
        color={accentColor}
      />

      <Text
        position={[0, floorY + WALL_HEIGHT - 0.4, -roomDepth / 2 + 0.22]}
        fontSize={0.38}
        color="#ffffff"
        anchorX="center"
      >
        {name}
      </Text>

      <CouchZone position={[-roomWidth * 0.28, floorY, roomDepth * 0.2]} />
      <ContextAssemblyZone position={[-roomWidth * 0.28, floorY, -roomDepth * 0.14]} />
      <PolicyGateZone position={[0, floorY, roomDepth * 0.26]} />
      <ExecutionZone position={[0, floorY, -0.1]} />
      <VerificationZone position={[roomWidth * 0.24, floorY, -0.08]} />
      <PersistenceZone position={[roomWidth * 0.28, floorY, -roomDepth * 0.24]} />
      <ErrorZone position={[roomWidth * 0.28, floorY, roomDepth * 0.22]} />
      <WorkerDesks
        count={deskCount}
        roomWidth={roomWidth}
        roomDepth={roomDepth}
        accentColor={accentColor}
        executiveStyle={executiveStyle}
      />
      <DirectorCornerOffice
        roomWidth={roomWidth}
        roomDepth={roomDepth}
        accentColor={accentColor}
      />
    </group>
  );
}

function LobbyMarker({
  position,
  label,
  color,
}: {
  position: Vec3;
  label: string;
  color: string;
}) {
  return (
    <group position={position}>
      <FloorMarker position={[0, 0, 0]} size={[2.4, 2.4]} color={color} label={label} />
      <ToonBox position={[0, 0.55, 0]} size={[0.5, 1.1, 0.5]} color="#334155" />
      <ToonBox position={[0, 1.18, 0.02]} size={[0.72, 0.22, 0.08]} color="#f8fafc" />
    </group>
  );
}

export function CentralLobbyRoom({ position = [0, 0, 0] }: RoomComponentProps) {
  const width = 15;
  const depth = 11;
  const floorY = 0;

  return (
    <group position={position}>
      <ToonBox position={[0, -0.12, 0]} size={[width + 0.8, 0.24, depth + 0.8]} color="#0f172a" />
      <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, floorY, 0]}>
        <planeGeometry args={[width, depth]} />
        <meshToonMaterial color="#f8fafc" />
      </mesh>
      <gridHelper args={[16, 16, "#94a3b8", "#cbd5e1"]} position={[0, floorY + 0.02, 0]} />

      <ToonBox position={[0, 1.6, -depth / 2 + 0.14]} size={[width, 3.2, 0.28]} color="#1e293b" />
      <GlassBox position={[-width / 2 + 0.14, 1.2, 0]} size={[0.28, 2.4, depth]} />
      <GlassBox position={[width / 2 - 0.14, 1.2, 0]} size={[0.28, 2.4, depth]} />

      <Text position={[0, 2.5, -depth / 2 + 0.24]} fontSize={0.46} color="#e2e8f0" anchorX="center">
        Central Lobby
      </Text>

      <ToonBox position={[0, 0.58, -0.3]} size={[3.8, 0.14, 1.8]} color="#475569" />
      <mesh position={[-1.35, 0.3, -0.55]}>
        <cylinderGeometry args={[0.16, 0.16, 0.56, 12]} />
        <meshToonMaterial color="#94a3b8" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>
      <mesh position={[1.35, 0.3, -0.55]}>
        <cylinderGeometry args={[0.16, 0.16, 0.56, 12]} />
        <meshToonMaterial color="#94a3b8" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>
      <mesh position={[-1.35, 0.3, 0.55]}>
        <cylinderGeometry args={[0.16, 0.16, 0.56, 12]} />
        <meshToonMaterial color="#94a3b8" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>
      <mesh position={[1.35, 0.3, 0.55]}>
        <cylinderGeometry args={[0.16, 0.16, 0.56, 12]} />
        <meshToonMaterial color="#94a3b8" />
        <Outlines thickness={0.02} color={OUTLINE_COLOR} />
      </mesh>

      <LobbyMarker position={[-4.2, floorY, 2.5]} label="Quest Kiosk" color="#ef4444" />
      <LobbyMarker position={[4.3, floorY, 2.5]} label="Memo Board" color="#3b82f6" />
      <LobbyMarker position={[0, floorY, 3.2]} label="Deal Board" color="#f59e0b" />
    </group>
  );
}

export function GlassCorridor({ position, size }: CorridorProps) {
  return (
    <group position={position}>
      <mesh receiveShadow position={[0, -0.04, 0]}>
        <boxGeometry args={[size[0], 0.08, size[2]]} />
        <meshToonMaterial color="#cbd5e1" />
      </mesh>
      <GlassBox position={[0, size[1] / 2, 0]} size={size} />
    </group>
  );
}
