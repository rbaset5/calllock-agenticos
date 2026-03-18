"use client";

import { DepartmentRoom, type RoomComponentProps } from "./shared";

export default function ExecutiveSuite(props: RoomComponentProps) {
  return (
    <DepartmentRoom
      {...props}
      roomId="executive_suite"
      name="Executive Suite"
      accentColor="#d4a43a"
      wallColor="#5b4624"
      size={[14, 10]}
      deskCount={4}
      elevated
      executiveStyle
    />
  );
}
