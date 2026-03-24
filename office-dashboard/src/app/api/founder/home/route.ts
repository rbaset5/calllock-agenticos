import {
  createFounderProxyResponse,
  proxyFounderRequest,
} from "@/lib/founder-api";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const upstream = await proxyFounderRequest("/founder/home", {
    tenantId: url.searchParams.get("tenant_id"),
  });

  return createFounderProxyResponse(upstream);
}
