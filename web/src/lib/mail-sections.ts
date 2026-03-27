import { assignBucket, triageSort, followUpSort, type BucketAssignment, type TriageableCall } from "@/lib/triage"

export type MailDisplaySection =
  | "ESCALATED_BY_AI"
  | "NEW_LEADS"
  | "FOLLOW_UPS"
  | "BOOKED_BY_AI"
  | "OTHER_AI_HANDLED"

export function getDisplaySection(
  call: TriageableCall,
  assignment: BucketAssignment = assignBucket(call)
): MailDisplaySection {
  if (assignment.bucket === "ACTION_QUEUE" && assignment.subGroup === "FOLLOW_UP") {
    return "FOLLOW_UPS"
  }
  if (assignment.bucket === "ACTION_QUEUE") return "NEW_LEADS"
  if (assignment.handledReason === "escalated") return "ESCALATED_BY_AI"
  if (assignment.handledReason === "booked") return "BOOKED_BY_AI"
  return "OTHER_AI_HANDLED"
}

interface MailSections<T extends TriageableCall> {
  ESCALATED_BY_AI: T[]
  NEW_LEADS: T[]
  FOLLOW_UPS: T[]
  BOOKED_BY_AI: T[]
  OTHER_AI_HANDLED: T[]
}

function newestFirst<T extends TriageableCall>(calls: T[]): T[] {
  return [...calls].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )
}

export function partitionMailSections<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): MailSections<T> {
  const escalated: T[] = []
  const newLeads: T[] = []
  const followUps: T[] = []
  const booked: T[] = []
  const otherHandled: T[] = []

  for (const call of calls) {
    const assignment = assignBucket(call)
    const section = getDisplaySection(call, assignment)
    if (section === "ESCALATED_BY_AI") escalated.push(call)
    else if (section === "NEW_LEADS") newLeads.push(call)
    else if (section === "FOLLOW_UPS") followUps.push(call)
    else if (section === "BOOKED_BY_AI") booked.push(call)
    else otherHandled.push(call)
  }

  return {
    ESCALATED_BY_AI: newestFirst(escalated),
    NEW_LEADS: triageSort(newLeads, now),
    FOLLOW_UPS: followUpSort(followUps),
    BOOKED_BY_AI: newestFirst(booked),
    OTHER_AI_HANDLED: newestFirst(otherHandled),
  }
}

export function orderCallsForMail<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): T[] {
  const sections = partitionMailSections(calls, now)
  return [
    ...sections.ESCALATED_BY_AI,
    ...sections.NEW_LEADS,
    ...sections.FOLLOW_UPS,
    ...sections.BOOKED_BY_AI,
    ...sections.OTHER_AI_HANDLED,
  ]
}

export function getDefaultSelectedId<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): string | null {
  const sections = partitionMailSections(calls, now)
  return (
    sections.ESCALATED_BY_AI[0]?.id ??
    sections.NEW_LEADS[0]?.id ??
    sections.FOLLOW_UPS[0]?.id ??
    sections.BOOKED_BY_AI[0]?.id ??
    sections.OTHER_AI_HANDLED[0]?.id ??
    null
  )
}
