import { NextResponse } from "next/server";

const SERVICES = [
  { name: "harness", url: "https://calllock-harness.onrender.com/health" },
  { name: "server", url: "https://calllock-server.onrender.com/health" },
];

const TIMEOUT_MS = 8_000;

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const results = await Promise.allSettled(
    SERVICES.map(async (svc) => {
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
