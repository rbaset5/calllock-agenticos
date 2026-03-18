"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function GrowthMarketingRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      roomId="growth_marketing_room"
      name="Growth Marketing"
      accentColor="#8B5CF6"
      wallColor="#6d28d9"
      size={[12.5, 8.5]}
      deskCount={6}
    />
  );
}
