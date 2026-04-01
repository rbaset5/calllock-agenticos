import { NextResponse } from "next/server";

const TIMEOUT_MS = 8_000;

function healthUrlFromBase(baseUrl: string | undefined): string | null {
  if (!baseUrl) return null;
  return `${baseUrl.replace(/\/$/, "")}/health`;
}

function configuredServices() {
  const services = [
    {
      name: "harness",
      url:
        process.env.KEEPALIVE_HARNESS_HEALTH_URL ??
        healthUrlFromBase(process.env.HARNESS_BASE_URL) ??
        "https://calllock-harness.onrender.com/health",
    },
    {
      name: "server",
      url:
        process.env.KEEPALIVE_SERVER_HEALTH_URL ??
        healthUrlFromBase(process.env.CALLLOCK_SERVER_BASE_URL) ??
        "https://calllock-server.onrender.com/health",
    },
  ];

  return services.filter((svc) => Boolean(svc.url));
}

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const services = configuredServices();
  if (services.length === 0) {
    return NextResponse.json({ error: "No keep-alive targets configured" }, { status: 500 });
  }

  const results = await Promise.allSettled(
    services.map(async (svc) => {
      const start = Date.now();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
      try {
        const res = await fetch(svc.url, { signal: controller.signal });
        return { name: svc.name, status: res.status, ms: Date.now() - start };
      } catch (err) {
        return {
          name: svc.name,
          status: 0,
          ms: Date.now() - start,
          error: err instanceof Error ? err.message : "unknown",
        };
      } finally {
        clearTimeout(timeout);
      }
    })
  );

  const pings = results.map((r) =>
    r.status === "fulfilled" ? r.value : { name: "unknown", status: 0, error: "rejected" }
  );

  const allHealthy = pings.every((p) => p.status === 200);

  return NextResponse.json(
    { ok: allHealthy, pings, timestamp: new Date().toISOString() },
    { status: allHealthy ? 200 : 207 }
  );
}
