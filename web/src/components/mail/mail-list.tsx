"use client"

import { formatDistanceToNow } from "date-fns"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { getUrgencyVariant } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Call } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  hasMore?: boolean
  isLoadingMore?: boolean
  onLoadMore?: () => void
  loadMoreError?: string | null
  emptyMessage?: string
}

export function MailList({
  items,
  selected,
  onSelect,
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
  loadMoreError,
  emptyMessage = "No calls found",
}: MailListProps) {
  return (
    <ScrollArea className="h-screen">
      <div className="flex flex-col gap-2 p-4 pt-0">
        {items.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            {emptyMessage}
          </div>
        ) : null}
        {items.map((item) => (
          <button
            key={item.id}
            className={cn(
              "flex flex-col items-start gap-2 rounded-lg border p-3 text-left text-sm transition-all hover:bg-accent",
              selected === item.id && "bg-muted"
            )}
            onClick={() => onSelect(item.id)}
          >
            <div className="flex w-full flex-col gap-1">
              <div className="flex items-center">
                <div className="flex items-center gap-2">
                  <div className="font-semibold">
                    {item.customerName || item.customerPhone || "Unknown"}
                  </div>
                  {!item.read && (
                    <span className="flex h-2 w-2 rounded-full bg-blue-600" />
                  )}
                </div>
                <div
                  className={cn(
                    "ml-auto text-xs",
                    selected === item.id
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {formatDistanceToNow(new Date(item.createdAt), {
                    addSuffix: true,
                  })}
                </div>
              </div>
              <div className="text-xs font-medium">
                {item.problemDescription
                  ? item.problemDescription.substring(0, 80)
                  : item.hvacIssueType || "Missed call"}
              </div>
            </div>
            {item.customerPhone && (
              <div className="text-xs text-muted-foreground">
                {item.customerPhone}
              </div>
            )}
            <div className="flex items-center gap-2">
              <Badge variant={getUrgencyVariant(item.urgency)}>
                {item.urgency}
              </Badge>
              {item.appointmentBooked && (
                <Badge variant="outline">Booked</Badge>
              )}
              {item.isSafetyEmergency && (
                <Badge variant="destructive">Safety</Badge>
              )}
              {item.endCallReason === "callback_later" && (
                <Badge variant="secondary">Callback</Badge>
              )}
            </div>
          </button>
        ))}
        {(hasMore || loadMoreError) && onLoadMore ? (
          <div className="pt-2">
            <Button
              variant="outline"
              className="w-full"
              onClick={onLoadMore}
              disabled={isLoadingMore}
            >
              {isLoadingMore
                ? "Loading older calls..."
                : loadMoreError
                  ? "Retry loading older calls"
                  : "Load more calls"}
            </Button>
            {loadMoreError ? (
              <p className="mt-2 text-xs text-destructive">
                {loadMoreError}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
