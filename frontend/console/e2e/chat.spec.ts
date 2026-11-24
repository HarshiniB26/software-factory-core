import { expect, test } from "@playwright/test";

test("a described issue opens a pull request", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What should we change?" })).toBeVisible();
  await page.getByRole("button", { name: /Choose repository|Repository / }).click();
  await expect(page.getByRole("listbox", { name: "Repositories" })).toBeVisible();
  await expect(page.getByText("GitHub sign-in needs the OAuth app.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings → GitHub" })).toHaveAttribute("href", "/settings#github");
  await page.getByRole("option", { name: /local\/sample/ }).click();
  await expect(page.getByRole("button", { name: "Repository local/sample" })).toBeVisible();
  await page.getByPlaceholder("Describe the issue").fill("Add a health check that returns ok");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Pull request #1")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A person merges this pull request.").first()).toBeVisible();
  await expect(page.getByText("Quality gates finished")).toBeVisible();
  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByRole("heading", { name: "Runs", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Registry" }).click();
  await expect(page.getByText("agent.worker@0.3.0")).toBeVisible();
  await page.getByRole("link", { name: "Repositories" }).click();
  await expect(page.getByRole("button", { name: "Connect" }).or(page.getByRole("button", { name: "Connected" })).first()).toBeVisible();
});

test("board and inbox show varied work", async ({ page }) => {
  await page.goto("/board");
  await expect(page.getByRole("heading", { name: "Board" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Needs input" })).toBeVisible();
  await expect(page.getByText("Which tax region applies to EU invoices?")).toBeVisible();
  await page.goto("/inbox");
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  await expect(page.getByText("Which tax region should EU invoices use?")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
});
