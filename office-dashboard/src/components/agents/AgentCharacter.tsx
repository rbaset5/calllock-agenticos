"use client";

import { Html, Outlines } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import { Group, Vector3 } from "three";

import type { Vec3 } from "@/components/rooms/shared";

type AgentCharacterProps = {
  name: string;
  accentColor: string;
  targetPosition: Vec3;
  taskDescription: string;
};

function lightenColor(hex: string, amount: number) {
  const value = hex.replace("#", "");
  const channels = [0, 2, 4].map((index) => {
    const base = Number.parseInt(value.slice(index, index + 2), 16);
    const next = Math.round(base + (255 - base) * amount);
    return next.toString(16).padStart(2, "0");
  });

  return `#${channels.join("")}`;
}

export default function AgentCharacter({
  name,
  accentColor,
  targetPosition,
  taskDescription,
}: AgentCharacterProps) {
  const groupRef = useRef<Group>(null);
  const targetVectorRef = useRef(new Vector3(...targetPosition));
  const frameTargetRef = useRef(new Vector3(...targetPosition));
  const bobSeedRef = useRef(Math.random() * Math.PI * 2);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    targetVectorRef.current.set(...targetPosition);
  }, [targetPosition]);

  useFrame((state, delta) => {
    const group = groupRef.current;
    if (!group) {
      return;
    }

    const bobOffset = Math.sin(state.clock.elapsedTime * 1.8 + bobSeedRef.current) * 0.08;
    frameTargetRef.current.set(
      targetVectorRef.current.x,
      targetVectorRef.current.y + bobOffset,
      targetVectorRef.current.z
    );
    group.position.lerp(frameTargetRef.current, 1 - Math.exp(-delta * 6));
  });

  const headColor = lightenColor(accentColor, 0.45);

  return (
    <group
      ref={groupRef}
      position={targetPosition}
      onPointerOver={(event) => {
        event.stopPropagation();
        setIsHovered(true);
      }}
      onPointerOut={() => setIsHovered(false)}
    >
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

      {isHovered ? (
        <Html position={[0, 1.95, 0]} center distanceFactor={12}>
          <div className="min-w-40 rounded-xl border border-white/15 bg-slate-950/90 px-3 py-2 text-left text-xs text-slate-100 shadow-2xl">
            <p className="font-semibold text-white">{name}</p>
            <p className="mt-1 text-slate-300">{taskDescription}</p>
          </div>
        </Html>
      ) : null}
    </group>
  );
}
