import { expect, test } from "@playwright/test";

test("a described issue opens a pull request", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What should we change?" })).toBeVisible();
  await page.getByPlaceholder("Describe the issue").fill("Add a health check that returns ok");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Pull request #")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("A person merges this pull request.")).toBeVisible();
  await expect(page.getByText("Quality gates finished")).toBeVisible();
});
