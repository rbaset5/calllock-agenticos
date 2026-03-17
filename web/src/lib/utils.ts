import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { UrgencyTier } from "@/types/call"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getUrgencyVariant(
  urgency: UrgencyTier | string
): "destructive" | "outline" | "secondary" | "default" {
  switch (urgency) {
    case "LifeSafety":
    case "Urgent":
      return "destructive"
    case "Estimate":
      return "outline"
    default:
      return "secondary"
  }
}
