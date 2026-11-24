import { describe, expect, it } from "vitest";
import { filterRepos, issueTarget } from "./repo-picker";
import type { Repo } from "./types";

const repos: Repo[] = [
  {
    owner: "local",
    name: "sample",
    full_name: "local/sample",
    description: "Bundled sample service",
    path: "/tmp/sample",
    kind: "local",
  },
  {
    owner: "acme",
    name: "billing",
    full_name: "acme/billing",
    description: "Checkout, tax, and coupons",
    path: null,
    kind: "fixture",
  },
];

describe("composer repository picker", () => {
  it("filters by name and description", () => {
    expect(filterRepos(repos, "bill").map((repo) => repo.full_name)).toEqual(["acme/billing"]);
    expect(filterRepos(repos, "sample").map((repo) => repo.full_name)).toEqual(["local/sample"]);
    expect(filterRepos(repos, "  ")).toHaveLength(2);
  });

  it("uses the checkout path when the repo has one", () => {
    expect(issueTarget(repos[0])).toBe("/tmp/sample");
    expect(issueTarget(repos[1])).toBe("acme/billing");
    expect(issueTarget(null)).toBeNull();
  });
});
