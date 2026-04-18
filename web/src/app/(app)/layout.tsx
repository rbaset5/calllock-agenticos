import type { ReactNode } from "react";

export default function AppLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <div className="dark h-dvh overflow-hidden bg-[#0e0e0e] text-[#e7e5e4]">
      {children}
    </div>
  );
}
