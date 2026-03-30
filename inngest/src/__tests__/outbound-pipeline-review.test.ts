import { beforeEach, describe, expect, it, vi } from "vitest";

const { postToOutboundFeed } = vi.hoisted(() => ({
  postToOutboundFeed: vi.fn(async () => undefined),
}));

vi.mock("../functions/outbound-projector.js", () => ({
  postToOutboundFeed,
}));

import { runOutboundPipelineReview } from "../functions/outbound-pipeline-review.js";

describe("outbound pipeline review", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.HARNESS_BASE_URL = "http://localhost:8000";
    process.env.HARNESS_EVENT_SECRET = "";
  });

  it("test_zero_dials_alert_fires_on_calling_day", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          date: "2026-03-30",
          calling_day: true,
          zero_dials_alert: true,
          scoreboard: { daily_dials: 0 },
          warm_leads_missing_next_step: [],
          sections: { recommended_actions: [] },
        }),
      })) as any,
    );

    await runOutboundPipelineReview({
      run: async (_label: string, fn: () => Promise<unknown>) => fn(),
    } as any);

    expect(postToOutboundFeed).toHaveBeenCalledTimes(2);
    expect(postToOutboundFeed.mock.calls[1][0].title).toContain("Zero Dials Alert");
  });

  it("test_no_alert_on_rest_day", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          date: "2026-03-30",
          calling_day: false,
          zero_dials_alert: false,
          scoreboard: { daily_dials: 0 },
          warm_leads_missing_next_step: [],
          sections: { recommended_actions: [] },
        }),
      })) as any,
    );

    await runOutboundPipelineReview({
      run: async (_label: string, fn: () => Promise<unknown>) => fn(),
    } as any);

    expect(postToOutboundFeed).toHaveBeenCalledTimes(1);
  });

  it("test_warm_leads_without_next_step", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          date: "2026-03-30",
          calling_day: true,
          zero_dials_alert: false,
          scoreboard: { daily_dials: 12 },
          warm_leads_missing_next_step: [
            { business_name: "A1 Mechanical", stage: "callback", metro: "Phoenix" },
            { business_name: "Blue Sky HVAC", stage: "interested", metro: "Dallas" },
          ],
          sections: { recommended_actions: ["Set next action dates"] },
        }),
      })) as any,
    );

    await runOutboundPipelineReview({
      run: async (_label: string, fn: () => Promise<unknown>) => fn(),
    } as any);

    expect(postToOutboundFeed).toHaveBeenCalledTimes(1);
    const embed = postToOutboundFeed.mock.calls[0][0];
    expect(embed.description).toContain("A1 Mechanical");
    expect(embed.description).toContain("Blue Sky HVAC");
  });
});
