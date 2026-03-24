import FounderNav from "@/components/founder/FounderNav";
import BlockedWorkPanel from "@/components/founder/BlockedWorkPanel";

type BlockedWorkPageProps = {
  searchParams?: {
    tenant_id?: string;
  };
};

export default function BlockedWorkPage({
  searchParams,
}: BlockedWorkPageProps) {
  const tenantId = searchParams?.tenant_id ?? null;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#172033_0%,#0f172a_48%,#020617_100%)] text-slate-100">
      <FounderNav currentPath="/blocked-work" tenantId={tenantId} />
      <section className="mx-auto max-w-6xl px-6 py-10">
        <BlockedWorkPanel tenantId={tenantId} />
      </section>
    </main>
  );
}
