import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/approvals", label: "Approvals" },
  { href: "/blocked-work", label: "Blocked Work" },
];

type FounderNavProps = {
  currentPath?: string;
  tenantId?: string | null;
};

export default function FounderNav({
  currentPath = "/",
  tenantId = null,
}: FounderNavProps) {
  return (
    <nav className="sticky top-0 z-10 border-b border-white/10 bg-slate-950/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">
            Founder MVP
          </p>
          <h1 className="mt-1 text-lg font-semibold text-white">
            CallLock Operating Surface
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {NAV_ITEMS.map((item) => {
            const isActive = currentPath === item.href;

            return (
              <Link
                key={item.href}
                href={{
                  pathname: item.href,
                  query: tenantId ? { tenant_id: tenantId } : undefined,
                }}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-cyan-400/15 text-cyan-100 ring-1 ring-cyan-300/30"
                    : "bg-white/5 text-slate-200 ring-1 ring-white/10 hover:bg-white/10"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
