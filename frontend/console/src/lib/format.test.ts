import { describe, expect, it } from "vitest";
import { compactGoal, eventLabel, isFixturePublish, pullHref, repoLabel, statusTone } from "./format";

describe("run presentation", () => {
  it("names pipeline events in product language", () => {
    expect(eventLabel("gates.finished")).toBe("Quality gates finished");
    expect(eventLabel("custom.event")).toBe("custom event");
  });

  it("keeps fixture pull requests inside the run", () => {
    expect(pullHref("https://example.test/factory/request-1/pull/1", "abc")).toBe("/runs/abc");
    expect(isFixturePublish("https://example.test/factory/request-1/pull/1")).toBe(true);
    expect(pullHref("https://github.com/acme/app/pull/4", "abc")).toContain("github.com");
  });

  it("hides the sample checkout path and repeated goals", () => {
    expect(repoLabel("/tmp/examples/sample-repo")).toBe("local/sample");
    expect(compactGoal("Add a health check\nAdd a health check")).toBe("Add a health check");
  });

  it("maps status to a tone", () => {
    expect(statusTone("completed")).toBe("ok");
    expect(statusTone("awaiting_approval")).toBe("wait");
    expect(statusTone("failed")).toBe("bad");
  });
});
