import {
  founderEndpoints,
  proxyFounderEndpoint,
} from "@/lib/founder-api";

export async function GET(request: Request) {
  return proxyFounderEndpoint(request, founderEndpoints.home);
}
