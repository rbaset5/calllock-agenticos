"use client"

import * as React from "react"
import { ChevronLeft, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { Call } from "@/types/call"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"

interface MailProps {
  initialCalls: Call[]
}

export function Mail({ initialCalls }: MailProps) {
  const [filter, setFilter] = React.useState<"all" | "unread">("all")
  const [mobileView, setMobileView] = React.useState<"list" | "detail">("list")
  const [selectedId, setSelectedId] = React.useState<string | null>(
    initialCalls[0]?.id ?? null
  )

  const { readIds, markAsRead } = useReadState()
  const calls = useRealtimeCalls(initialCalls, readIds)

  const filteredCalls = filter === "unread" ? calls.filter((c) => !c.read) : calls
  const selectedCall = calls.find((c) => c.id === selectedId) ?? null

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
    setMobileView("detail")
  }

  return (
    <TooltipProvider delayDuration={0}>
      {/* Mobile layout */}
      <div className="flex h-full flex-col md:hidden">
        {mobileView === "list" ? (
          <Tabs defaultValue="all">
            <div className="flex h-[52px] items-center px-4">
              <h1 className="text-lg font-semibold">Calls</h1>
              <TabsList className="ml-auto">
                <TabsTrigger
                  value="all"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("all")}
                >
                  All
                </TabsTrigger>
                <TabsTrigger
                  value="unread"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("unread")}
                >
                  Unread
                </TabsTrigger>
              </TabsList>
            </div>
            <Separator />
            <div className="bg-background/95 p-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <form>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Search" className="pl-8" />
                </div>
              </form>
            </div>
            <TabsContent value="all" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
            <TabsContent value="unread" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
          </Tabs>
        ) : (
          <div className="flex h-full flex-col">
            <div className="flex h-[52px] items-center gap-2 px-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileView("list")}
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Back</span>
              </Button>
              <div className="text-sm font-medium">Call Details</div>
            </div>
            <Separator />
            <div className="min-h-0 flex-1">
              <MailDisplay call={selectedCall} />
            </div>
          </div>
        )}
      </div>

      {/* Desktop layout */}
      <ResizablePanelGroup
        orientation="horizontal"
        className="hidden h-full max-h-screen items-stretch md:flex"
      >
        <ResizablePanel id="mail-list" defaultSize={40} minSize={30}>
          <Tabs defaultValue="all">
            <div className="flex h-[52px] items-center px-4">
              <h1 className="text-xl font-bold">Calls</h1>
              <TabsList className="ml-auto">
                <TabsTrigger
                  value="all"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("all")}
                >
                  All
                </TabsTrigger>
                <TabsTrigger
                  value="unread"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("unread")}
                >
                  Unread
                </TabsTrigger>
              </TabsList>
            </div>
            <Separator />
            <div className="bg-background/95 p-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <form>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Search" className="pl-8" />
                </div>
              </form>
            </div>
            <TabsContent value="all" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
            <TabsContent value="unread" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
          </Tabs>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel id="mail-display" defaultSize={60} minSize={30}>
          <MailDisplay call={selectedCall} />
        </ResizablePanel>
      </ResizablePanelGroup>
    </TooltipProvider>
  )
}
