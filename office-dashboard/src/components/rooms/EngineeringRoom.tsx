"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function EngineeringRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      roomId="engineering_room"
      name="Engineering Room"
      accentColor="#10B981"
      wallColor="#047857"
      size={[10.5, 8]}
      deskCount={4}
    />
  );
}
