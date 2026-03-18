"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";

import OfficeLayout from "@/components/rooms/OfficeLayout";

export default function OfficeScene() {
  return (
    <Canvas
      shadows
      camera={{ position: [0, 18, 28], fov: 42 }}
    >
      <color attach="background" args={["#020617"]} />
      <fog attach="fog" args={["#020617", 28, 60]} />
      <ambientLight intensity={1.1} />
      <directionalLight castShadow intensity={1.5} position={[18, 24, 14]} shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
      <directionalLight intensity={0.45} position={[-14, 12, -10]} color="#93c5fd" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.14, 0]} receiveShadow>
        <planeGeometry args={[64, 64]} />
        <meshStandardMaterial color="#0f172a" />
      </mesh>
      <gridHelper args={[64, 32, "#1e293b", "#0f172a"]} position={[0, -0.12, 0]} />
      <OfficeLayout />
      <OrbitControls enablePan enableZoom maxPolarAngle={Math.PI / 2.05} minDistance={12} maxDistance={42} target={[0, 2, 0]} />
    </Canvas>
  );
}
