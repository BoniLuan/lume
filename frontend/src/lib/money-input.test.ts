import { describe, expect, it } from "vitest";

import { sanitizeMoneyInput } from "./money-input";

describe("sanitizeMoneyInput", () => {
  it("removes letters and limits decimal precision", () => {
    expect(sanitizeMoneyInput("R$ 47abc,90123")).toBe("47.9012");
  });

  it("normalizes pasted grouping and decimal separators", () => {
    expect(sanitizeMoneyInput("1.234,56")).toBe("1234.56");
  });

  it("allows a negative opening balance only when requested", () => {
    expect(sanitizeMoneyInput("-120.50")).toBe("120.50");
    expect(sanitizeMoneyInput("-120.50", true)).toBe("-120.50");
  });
});
