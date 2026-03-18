"use client";

import { CameraControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useEffect, useRef } from "react";

import AgentManager from "@/components/agents/AgentManager";
import HandoffAnimation from "@/components/agents/HandoffAnimation";
import DailyMemo from "@/components/overlays/DailyMemo";
import QuestLog from "@/components/overlays/QuestLog";
import {
  ORBITAL_CAMERA_VIEW,
  type Vec3,
} from "@/components/rooms/shared";
import OfficeLayout from "@/components/rooms/OfficeLayout";
import { useCameraStore } from "@/store/camera-store";

type OfficeSceneProps = {
  showQuestLog?: boolean;
  showDailyMemo?: boolean;
};

export default function OfficeScene({
  showQuestLog = false,
  showDailyMemo = false,
}: OfficeSceneProps) {
  const controlsRef = useRef<React.ElementRef<typeof CameraControls>>(null);
  const currentView = useCameraStore((state) => state.currentView);
  const flyToOrbital = useCameraStore((state) => state.flyToOrbital);

  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) {
      return;
    }

    const nextPosition: Vec3 =
      currentView === "orbital"
        ? ORBITAL_CAMERA_VIEW.position
        : currentView.position;
    const nextTarget: Vec3 =
      currentView === "orbital"
        ? ORBITAL_CAMERA_VIEW.target
        : currentView.target;

    void controls.setLookAt(
      nextPosition[0],
      nextPosition[1],
      nextPosition[2],
      nextTarget[0],
      nextTarget[1],
      nextTarget[2],
      true
    );
  }, [currentView]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        flyToOrbital();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [flyToOrbital]);

  return (
    <Canvas
      shadows
      camera={{ position: ORBITAL_CAMERA_VIEW.position, fov: 42 }}
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
      <AgentManager />
      <HandoffAnimation />
      <QuestLog visible={showQuestLog} />
      <DailyMemo visible={showDailyMemo} />
      <CameraControls
        ref={controlsRef}
        makeDefault
        smoothTime={1}
        minDistance={5}
        maxDistance={42}
        maxPolarAngle={Math.PI / 2.02}
      />
    </Canvas>
  );
}
