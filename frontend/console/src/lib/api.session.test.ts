import { describe, expect, it } from "vitest";
import { sessionFromRedirect } from "./api";

describe("sessionFromRedirect", () => {
  it("keeps the GitHub login token and removes it from the address", () => {
    const found = sessionFromRedirect("?token=signed-session&next=inbox");
    expect(found.token).toBe("signed-session");
    expect(found.search).toBe("?next=inbox");
  });

  it("leaves a normal visit unchanged", () => {
    expect(sessionFromRedirect("")).toEqual({ token: null, search: "" });
  });
});
