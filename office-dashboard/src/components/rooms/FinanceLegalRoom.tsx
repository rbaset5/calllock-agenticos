"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function FinanceLegalRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      roomId="finance_legal_room"
      name="Finance / Legal"
      accentColor="#6B7280"
      wallColor="#374151"
      size={[9.8, 7.5]}
      deskCount={3}
    />
  );
}
