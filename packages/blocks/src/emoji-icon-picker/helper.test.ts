/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { stringToEmoji } from "./helper";

describe("stringToEmoji", () => {
  it("passes raw emoji glyphs through unchanged (BUG-07: type seeds store the literal character)", () => {
    expect(stringToEmoji("🏔")).toBe("🏔");
    expect(stringToEmoji("👍")).toBe("👍");
  });

  it("still decodes the dash-separated decimal code point storage format", () => {
    expect(stringToEmoji("128077")).toBe("👍");
    expect(stringToEmoji("128077-128078")).toBe("👍👎");
  });

  it("returns an empty string for empty input", () => {
    expect(stringToEmoji("")).toBe("");
  });
});
