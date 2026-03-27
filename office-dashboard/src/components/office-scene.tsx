"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";

function PlaceholderCube() {
  return (
    <mesh castShadow receiveShadow rotation={[0.4, 0.8, 0]}>
      <boxGeometry args={[1.4, 1.4, 1.4]} />
      <meshStandardMaterial color="#f97316" metalness={0.25} roughness={0.35} />
    </mesh>
  );
}

export default function OfficeScene() {
  return (
    <Canvas camera={{ position: [3.5, 3, 4.5], fov: 50 }}>
      <ambientLight intensity={0.75} />
      <directionalLight castShadow intensity={1.4} position={[5, 7, 4]} />
      <gridHelper args={[12, 12, "#334155", "#1e293b"]} position={[0, -1.4, 0]} />
      <PlaceholderCube />
      <OrbitControls enablePan enableZoom maxPolarAngle={Math.PI / 2.1} minDistance={2.5} maxDistance={10} />
    </Canvas>
  );
}
