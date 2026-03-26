"use client";

import { ThreeEvent } from "@react-three/fiber";

import CentralLobby from "./CentralLobby";
import CustomerSuccessRoom from "./CustomerSuccessRoom";
import EngineeringRoom from "./EngineeringRoom";
import ExecutiveSuite from "./ExecutiveSuite";
import FinanceLegalRoom from "./FinanceLegalRoom";
import GrowthMarketingRoom from "./GrowthMarketingRoom";
import ProductRoom from "./ProductRoom";
import { GlassCorridor, ROOM_POSITIONS, type RoomKey } from "./shared";
import { useCameraStore } from "@/store/camera-store";

export default function OfficeLayout() {
  const flyToRoom = useCameraStore((state) => state.flyToRoom);

  function handleRoomClick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    let node: typeof event.eventObject | null = event.eventObject;
    let roomId: RoomKey | undefined;

    while (node) {
      const candidate = node.userData?.roomId as RoomKey | undefined;
      if (candidate) {
        roomId = candidate;
        break;
      }
      node = node.parent;
    }

    if (roomId) {
      flyToRoom(roomId);
    }
  }

  return (
    <group>
      <group onClick={handleRoomClick}>
        <ExecutiveSuite position={ROOM_POSITIONS.executive_suite} />
      </group>
      <group onClick={handleRoomClick}>
        <ProductRoom position={ROOM_POSITIONS.product_room} />
      </group>
      <group onClick={handleRoomClick}>
        <FinanceLegalRoom position={ROOM_POSITIONS.finance_legal_room} />
      </group>
      <group onClick={handleRoomClick}>
        <CentralLobby position={ROOM_POSITIONS.central_lobby} />
      </group>
      <group onClick={handleRoomClick}>
        <EngineeringRoom position={ROOM_POSITIONS.engineering_room} />
      </group>
      <group onClick={handleRoomClick}>
        <GrowthMarketingRoom position={ROOM_POSITIONS.growth_marketing_room} />
      </group>
      <group onClick={handleRoomClick}>
        <CustomerSuccessRoom position={ROOM_POSITIONS.customer_success_room} />
      </group>

      <GlassCorridor position={[0, 1.15, 7.2]} size={[3.2, 2.3, 6]} />
      <GlassCorridor position={[-8.4, 1.15, 7.2]} size={[10.2, 2.3, 3]} />
      <GlassCorridor position={[8.4, 1.15, 7.2]} size={[10.2, 2.3, 3]} />

      <GlassCorridor position={[0, 1.15, -7.2]} size={[3.2, 2.3, 6.3]} />
      <GlassCorridor position={[-8.6, 1.15, -7.2]} size={[10.8, 2.3, 3]} />
      <GlassCorridor position={[8.6, 1.15, -7.2]} size={[10.8, 2.3, 3]} />

      <GlassCorridor position={[0, 1.15, 0]} size={[3.2, 2.3, 12]} />
      <GlassCorridor position={[0, 1.15, -11]} size={[3.2, 2.3, 3]} />
    </group>
  );
}
