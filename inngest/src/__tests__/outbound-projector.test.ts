import { describe, expect, it, vi } from "vitest";

import {
  buildDiscoveryEmbed,
  buildErrorEmbed,
  buildTestResultsEmbed,
  postToOutboundFeed,
} from "../functions/outbound-projector.js";

describe("outbound projector embeds", () => {
  it("formats discovery embeds", () => {
    const embed = buildDiscoveryEmbed({
      tenant_id: "00000000-0000-0000-0000-000000000001",
      ingested: 10,
      scored: 8,
      a_leads: 3,
      b_leads: 2,
      source_version: "outbound-scout-v1",
    });

    expect(embed.title).toContain("Batch Complete");
    expect(embed.fields?.find((field) => field.name === "Ingested")?.value).toBe("10");
  });

  it("formats probe result embeds", () => {
    const embed = buildTestResultsEmbed({
      tenant_id: "00000000-0000-0000-0000-000000000001",
      tested: 12,
      confirmed_weak: 7,
      answered: 2,
      source_version: "outbound-scout-v1",
    });

    expect(embed.title).toContain("Probe");
    expect(embed.fields?.find((field) => field.name === "Confirmed Weak")?.value).toBe("7");
  });

  it("formats error embeds", () => {
    const embed = buildErrorEmbed({
      tenant_id: "00000000-0000-0000-0000-000000000001",
      error_type: "twilio_error",
      error_message: "rate limited",
      source_version: "outbound-scout-v1",
    });

    expect(embed.color).toBe(0xef4444);
    expect(embed.description).toBe("rate limited");
  });
});

describe("postToOutboundFeed", () => {
  it("no-ops when webhook is missing", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const previous = process.env.DISCORD_OUTBOUND_FEED_WEBHOOK_URL;
    delete process.env.DISCORD_OUTBOUND_FEED_WEBHOOK_URL;

    await expect(
      postToOutboundFeed({ title: "x", description: "y", color: 1 }),
    ).resolves.toBeUndefined();
    expect(fetchSpy).not.toHaveBeenCalled();

    if (previous) {
      process.env.DISCORD_OUTBOUND_FEED_WEBHOOK_URL = previous;
    }
  });
});
