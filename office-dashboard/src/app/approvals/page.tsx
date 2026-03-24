import FounderNav from "@/components/founder/FounderNav";
import ApprovalsPanel from "@/components/founder/ApprovalsPanel";

type ApprovalsPageProps = {
  searchParams?: {
    tenant_id?: string;
  };
};

export default function ApprovalsPage({ searchParams }: ApprovalsPageProps) {
  const tenantId = searchParams?.tenant_id ?? null;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#172033_0%,#0f172a_48%,#020617_100%)] text-slate-100">
      <FounderNav currentPath="/approvals" tenantId={tenantId} />
      <section className="mx-auto max-w-6xl px-6 py-10">
        <ApprovalsPanel tenantId={tenantId} />
      </section>
    </main>
  );
}
