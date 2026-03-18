"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function CustomerSuccessRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      roomId="customer_success_room"
      name="Customer Success"
      accentColor="#F59E0B"
      wallColor="#b45309"
      size={[11.5, 8.2]}
      deskCount={5}
    />
  );
}
