import {
  createFounderProxyResponse,
  proxyFounderRequest,
} from "@/lib/founder-api";

type ApprovalRouteContext = {
  params: {
    approvalId: string;
  };
};

export async function POST(request: Request, context: ApprovalRouteContext) {
  const body = await request.text();
  const headers = new Headers();

  headers.set(
    "content-type",
    request.headers.get("content-type") ?? "application/json"
  );

  const actorId = request.headers.get("x-actor-id");
  if (actorId) {
    headers.set("x-actor-id", actorId);
  }

  const upstream = await proxyFounderRequest(
    `/approvals/${encodeURIComponent(context.params.approvalId)}`,
    {
      method: "POST",
      body,
      headers,
    }
  );

  return createFounderProxyResponse(upstream);
}
