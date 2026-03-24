import {
  proxyFounderApprovalDecision,
} from "@/lib/founder-api";

type ApprovalRouteContext = {
  params: {
    approvalId: string;
  };
};

export async function POST(request: Request, context: ApprovalRouteContext) {
  return proxyFounderApprovalDecision(request, context.params.approvalId);
}
