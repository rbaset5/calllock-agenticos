"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function CustomerSuccessRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      name="Customer Success"
      accentColor="#F59E0B"
      wallColor="#b45309"
      size={[11.5, 8.2]}
      deskCount={5}
    />
  );
}
