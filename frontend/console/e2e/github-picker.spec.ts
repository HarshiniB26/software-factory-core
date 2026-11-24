import { expect, test } from "@playwright/test";

const install = "https://github.com/apps/factory/installations/new";

test("composer lists mocked GitHub repos for a signed-in account", async ({ page }) => {
  await page.route("**/api/repos**", async (route) => {
    const url = route.request().url();
    if (url.includes("/branches")) {
      await route.fulfill({
        json: { branches: ["main", "release"], default: "main" },
      });
      return;
    }
    if (url.includes("/refresh")) {
      await route.fulfill({ json: payload() });
      return;
    }
    if (route.request().method() === "POST" && url.includes("/connect")) {
      await route.fulfill({
        json: {
          owner: "acme",
          name: "billing",
          full_name: "acme/billing",
          description: "Checkout",
          path: null,
          kind: "github",
          private: true,
          default_branch: "main",
          branch: "main",
        },
      });
      return;
    }
    await route.fulfill({ json: payload() });
  });

  await page.goto("/");
  await page.getByRole("button", { name: /Choose repository|Repository / }).click();
  await expect(page.getByText("ada")).toBeVisible();
  await expect(page.getByText("Local", { exact: true })).toBeVisible();
  await expect(page.getByText("GitHub", { exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: /acme\/billing/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Add repositories" })).toHaveAttribute("href", install);
  await page.getByRole("option", { name: /acme\/billing/ }).click();
  await expect(page.getByRole("button", { name: "Repository acme/billing" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Branch main" })).toBeVisible();
});

function payload() {
  return {
    repos: [
      {
        owner: "local",
        name: "sample",
        full_name: "local/sample",
        description: "Bundled sample",
        path: "/tmp/sample",
        kind: "local",
      },
      {
        owner: "acme",
        name: "billing",
        full_name: "acme/billing",
        description: "Checkout",
        path: null,
        kind: "github",
        private: true,
        default_branch: "main",
      },
    ],
    connected: null,
    mode: "fixture",
    oauth: true,
    github: { login: "ada", avatar_url: "", installed: true },
    install_url: install,
  };
}
