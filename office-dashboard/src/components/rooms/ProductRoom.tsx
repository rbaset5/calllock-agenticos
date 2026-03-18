"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function ProductRoom(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      name="Product Room"
      accentColor="#3B82F6"
      wallColor="#1d4ed8"
      size={[11.5, 8.5]}
      deskCount={7}
    />
  );
}
