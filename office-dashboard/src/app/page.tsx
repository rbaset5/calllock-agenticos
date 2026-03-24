import FounderNav from "@/components/founder/FounderNav";
import HomePanel from "@/components/founder/HomePanel";

type HomePageProps = {
  searchParams?: {
    tenant_id?: string;
  };
};

export default function Home({ searchParams }: HomePageProps) {
  const tenantId = searchParams?.tenant_id ?? null;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#172033_0%,#0f172a_48%,#020617_100%)] text-slate-100">
      <FounderNav currentPath="/" tenantId={tenantId} />
      <HomePanel tenantId={tenantId} />
    </main>
  );
}
