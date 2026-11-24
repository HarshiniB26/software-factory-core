import { expect, test } from "@playwright/test";

const runtime = { execution_mode: "live", provider: "personal", model: "coding-model", ready: true, usage_available: false, execution_isolation: "trusted-host", approval: "always", providers: [{ id: "personal", name: "Personal account", driver: "codex", enabled: true, models: ["coding-model", "other-model"] }] };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api", "");
    const payloads: Record<string, unknown> = {
      "/auth/me": { id: "operator", roles: ["admin", "approver", "requester"] },
      "/repos": { repos: [], connected: null, mode: "dev", oauth: false, github: null, install_url: null },
      "/requests": [], "/runtime": runtime,
      "/monitor": { healthy: true, health: { at: Date.now() / 1000, alerts: 0 }, alerts: [] },
      "/learning": { outcomes: [], candidates: [], evaluations: [], active: [], jobs: [] },
      "/modules": { installed: [], selected: {}, flags: {} },
      "/cost": { pull_requests: 0, estimated_usd: null, usage_available: false, series: [], success_rate: 0, average_duration_seconds: 0, by_role: [] },
      "/audit": { events: [], kill_switch: false },
      "/settings": { plan_approval: "always", clarification: "major", roles: {} },
    };
    if (path === "/requests/live-run/view") {
      await route.fulfill({ json: { request: { id: "live-run", title: "Fix checkout", status: "awaiting_approval", body: "Fix", target: "org/shop", created_at: new Date().toISOString() }, execution_mode: "live", project_type: "brownfield", stage: "approval", model: "coding-model", provider: "personal", active_seconds: 12, usage_available: false, plan_details: { summary: "Handle empty carts", acceptance_criteria: ["Empty cart returns a validation error"], verification: [["pytest", "tests/test_checkout.py"]], preserve: [], migration_steps: [], rollback: [] }, steps: [{ id: "fix", goal: "Update the checkout handler" }], events: [], questions: [], messages: [], diff: "", diff_kind: "unavailable", gates: [], prs: [], crew: [], logs: [], files: [], assumptions: [], risk: "low", risk_score: 0 } }); return;
    }
    await route.fulfill({ json: payloads[path] ?? {} });
  });
});

test("live run shows actual approval evidence without demo agents or scanners", async ({ page }) => {
  await page.goto("/runs/live-run");
  await expect(page.getByRole("heading", { name: "Fix checkout" })).toBeVisible();
  await expect(page.getByText("Handle empty carts")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve plan and commands" })).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Semgrep", { exact: true })).toHaveCount(0);
  await expect(page.getByText("claude-sonnet", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: "/tmp/factory-live-run-ui.png", fullPage: true });
});

test("settings discovers real provider models and saves a valid selection", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Execution runtime" })).toBeVisible();
  await page.getByLabel("Execution model").selectOption("other-model");
  const saved = page.waitForRequest((request) => request.url().endsWith("/api/runtime") && request.method() === "PUT");
  await page.getByRole("button", { name: "Save runtime" }).click();
  expect((await saved).postDataJSON()).toEqual({ provider: "personal", model: "other-model", approval: "always" });
  await expect(page.getByRole("status").filter({ hasText: "Saved. New requests" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Roles", exact: true })).toHaveCount(0);
});

test("operations shows monitor health and honest learning state", async ({ page }) => {
  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "Health and improvement" })).toBeVisible();
  await expect(page.getByText("Reporting", { exact: true })).toBeVisible();
  await expect(page.getByText("No candidates recorded yet.", { exact: false })).toBeVisible();
  await page.screenshot({ path: "/tmp/factory-operations-ui.png", fullPage: true });
});

test("composer asks only for the request and repository, not a workflow category", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByPlaceholder("Describe the issue")).toBeVisible();
  await expect(page.getByLabel("Workflow type")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Choose repository|Repository / })).toBeVisible();
});

test("live clarification requires the user's answer instead of a canned choice", async ({ page }) => {
  await page.route("**/api/inbox", (route) => route.fulfill({ json: { items: [{ id: "question-run", title: "Checkout behavior", question: "Should an empty cart return a validation error?", status: "parked", execution_mode: "live", kind: "question" }] } }));
  await page.goto("/inbox");
  await expect(page.getByText("Should an empty cart return a validation error?")).toBeVisible();
  await expect(page.getByRole("link", { name: "Answer in conversation" })).toHaveAttribute("href", "/runs/question-run");
  await expect(page.getByRole("button", { name: "Use the smallest change" })).toHaveCount(0);
});
