export interface ProcessCallPayload {
  call_id: string;
  tenant_id: string;
  transcript?: string;
  problem_description?: string;
}

export function validateProcessCallPayload(payload: ProcessCallPayload): string[] {
  const errors: string[] = [];
  if (!payload.call_id) errors.push("call_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  return errors;
}
