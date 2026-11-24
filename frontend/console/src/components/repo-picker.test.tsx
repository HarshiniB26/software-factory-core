import { RepoPicker } from "@/components/repo-picker";
import { GITHUB_OAUTH_NOTE } from "@/lib/repo-picker";
import type { Repo } from "@/lib/types";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(() => cleanup());

const sample: Repo = {
  owner: "local",
  name: "sample",
  full_name: "local/sample",
  description: "Bundled sample service",
  path: "/tmp/sample",
  kind: "local",
};

function Harness({ oauth = false }: { oauth?: boolean }) {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<Repo | null>(null);
  return (
    <MemoryRouter>
      <RepoPicker
        repos={[sample]}
        connected={current}
        oauth={oauth}
        open={open}
        onOpenChange={setOpen}
        onSelect={(fullName) => setCurrent(fullName === sample.full_name ? sample : null)}
      />
    </MemoryRouter>
  );
}

describe("RepoPicker", () => {
  it("chooses a repository from the composer chip", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Choose repository" }));
    fireEvent.click(screen.getByRole("option", { name: /local\/sample/ }));
    expect(screen.getByRole("button", { name: "Repository local/sample" })).toBeTruthy();
  });

  it("shows the OAuth note instead of a login link in dev mode", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Choose repository" }));
    expect(screen.getByRole("button", { name: "Connect GitHub" })).toBeTruthy();
    expect(screen.getByText(GITHUB_OAUTH_NOTE, { exact: false })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Settings → GitHub" }).getAttribute("href")).toBe("/settings#github");
    expect(screen.queryByRole("link", { name: "Connect GitHub" })).toBeNull();
  });

  it("links Connect GitHub when the OAuth app is configured", () => {
    render(<Harness oauth />);
    fireEvent.click(screen.getByRole("button", { name: "Choose repository" }));
    expect(screen.getByRole("link", { name: "Connect GitHub" }).getAttribute("href")).toBe("/api/auth/github/login");
    expect(screen.queryByText(GITHUB_OAUTH_NOTE, { exact: false })).toBeNull();
  });

  it("keeps the popover open when Connect GitHub has no OAuth app", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Choose repository" }));
    fireEvent.click(screen.getByRole("button", { name: "Connect GitHub" }));
    expect(screen.getByRole("dialog", { name: "Choose repository" })).toBeTruthy();
  });
});
