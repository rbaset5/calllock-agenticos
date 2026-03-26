import { create } from "zustand";

import {
  ROOM_CAMERA_VIEWS,
  type RoomKey,
  type Vec3,
} from "@/components/rooms/shared";

export type CameraRoomView = {
  room: RoomKey;
  position: Vec3;
  target: Vec3;
};

export type CameraView = "orbital" | CameraRoomView;

type CameraStore = {
  currentView: CameraView;
  flyToRoom: (roomId: RoomKey) => void;
  flyToOrbital: () => void;
};

export const useCameraStore = create<CameraStore>((set) => ({
  currentView: "orbital",
  flyToRoom: (roomId) =>
    set({
      currentView: {
        room: roomId,
        position: ROOM_CAMERA_VIEWS[roomId].position,
        target: ROOM_CAMERA_VIEWS[roomId].target,
      },
    }),
  flyToOrbital: () => set({ currentView: "orbital" }),
}));
