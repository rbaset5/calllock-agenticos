"use client";

import CentralLobby from "./CentralLobby";
import CustomerSuccessRoom from "./CustomerSuccessRoom";
import EngineeringRoom from "./EngineeringRoom";
import ExecutiveSuite from "./ExecutiveSuite";
import FinanceLegalRoom from "./FinanceLegalRoom";
import GrowthMarketingRoom from "./GrowthMarketingRoom";
import ProductRoom from "./ProductRoom";
import { GlassCorridor, ROOM_POSITIONS } from "./shared";

export default function OfficeLayout() {
  return (
    <group>
      <ExecutiveSuite position={ROOM_POSITIONS.executive_suite} />
      <ProductRoom position={ROOM_POSITIONS.product_room} />
      <FinanceLegalRoom position={ROOM_POSITIONS.finance_legal_room} />
      <CentralLobby position={ROOM_POSITIONS.central_lobby} />
      <EngineeringRoom position={ROOM_POSITIONS.engineering_room} />
      <GrowthMarketingRoom position={ROOM_POSITIONS.growth_marketing_room} />
      <CustomerSuccessRoom position={ROOM_POSITIONS.customer_success_room} />

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
