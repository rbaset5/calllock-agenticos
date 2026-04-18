import type { NextRequest } from "next/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

type PingResult = {
  name: string
  url: string
  ok: boolean
  status: number | null
  latencyMs: number
  error?: string
}

const KEEP_ALIVE_TARGETS = [
  {
    name: "calllock-server",
    url: "https://calllock-server.onrender.com/health",
  },
  {
    name: "calllock-harness",
    url: "https://calllock-harness.onrender.com/health",
  },
] as const

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return "Unknown error"
}

async function pingTarget(name: string, url: string): Promise<PingResult> {
  const startedAt = Date.now()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8_000)

  try {
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      headers: {
        "user-agent": "calllock-keep-alive/1.0",
      },
      signal: controller.signal,
    })

    await response.text()

    return {
      name,
      url,
      ok: response.ok,
      status: response.status,
      latencyMs: Date.now() - startedAt,
    }
  } catch (error) {
    return {
      name,
      url,
      ok: false,
      status: null,
      latencyMs: Date.now() - startedAt,
      error: getErrorMessage(error),
    }
  } finally {
    clearTimeout(timeout)
  }
}

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET
  const authHeader = request.headers.get("authorization")

  if (!cronSecret) {
    return Response.json(
      { error: "CRON_SECRET is not configured" },
      { status: 500 }
    )
  }

  if (authHeader !== `Bearer ${cronSecret}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 })
  }

  const results = await Promise.all(
    KEEP_ALIVE_TARGETS.map((target) => pingTarget(target.name, target.url))
  )

  console.info(
    "cron.keep_alive",
    JSON.stringify({
      invokedAt: new Date().toISOString(),
      results,
    })
  )

  return Response.json({
    ok: results.every((result) => result.ok),
    invokedAt: new Date().toISOString(),
    results,
  })
}
