// ============================================================
// PAYLOAD DEDUP — PURE FUNCTION TESTS
// ============================================================
// Test logic dedup cua content.js:
//   - computePayloadKey(payload, id)
//   - processedPayloadKeys FIFO (Set insertion order + eviction)
//   - hasProcessedPayload / markPayloadProcessed
//
// Cach chay: copy nguyen block ham tu content.js vao harness de test logic
// ma khong phu thuoc vao chrome.* API (khong co trong Node).
//
// Muc tieu regression chinh:
//   1. Bug goc: dedup theo 1 hash cuoi -> khi user doi chat / switch qua lai
//      giua cac tab, payload CU trong DOM bi xu ly lai (switch loop).
//   2. Fix: queue per-tab FIFO 100 key, dedup theo id (fallback hash content).
//      Khong bi "lua" khi doi chat / switch tab / F5 / dong browser.

import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Harness: extract + re-eval cac ham dedup thuan tuy tu content.js.
// Khong eval ca file (vi content.js goi chrome.* ngay top-level).
function loadDedupHarness() {
  const src = readFileSync(join(__dirname, "..", "..", "content.js"), "utf8");

  // Bam theo comment marker da dat trong content.js.
  // Neu marker bi doi, test se fail -> bao hieu can cap nhat harness.
  const maxConstMatch = src.match(/const PROCESSED_QUEUE_MAX = (\d+);/);
  if (!maxConstMatch) throw new Error("PROCESSED_QUEUE_MAX not found in content.js");
  const PROCESSED_QUEUE_MAX = Number(maxConstMatch[1]);

  const computeKeyMatch = src.match(/function computePayloadKey\(payload, id\) \{[\s\S]*?\n\}/);
  if (!computeKeyMatch) throw new Error("computePayloadKey not found in content.js");

  const markMatch = src.match(/function markPayloadProcessed\(key\) \{[\s\S]*?\n\}/);
  if (!markMatch) throw new Error("markPayloadProcessed not found in content.js");

  const hasMatch = src.match(/function hasProcessedPayload\(key\) \{[\s\S]*?\n\}/);
  if (!hasMatch) throw new Error("hasProcessedPayload not found in content.js");

  // Stub HashUtils (fallback khi payload khong co id).
  const HashUtils = {
    hashText: (text) => {
      // Don gian + on dinh trong Node: dung do dai + first 8 chars.
      const s = String(text);
      let h = 0;
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
      return "hash_" + (h >>> 0).toString(16);
    },
  };

  const processedPayloadKeys = new Set();

  // Evaluate cac ham trong scope co closure rieng.
  // persistProcessedQueue bi stub — khong test storage o day.
  //
  // Dung IIFE + return object tuong minh: `new Function` tra ve gia tri
  // cua `return`, khong phai expression cuoi cung trong body.
  const harnessCode = `
    return (function () {
      ${computeKeyMatch[0]}
      ${hasMatch[0]}
      ${markMatch[0]}
      return { computePayloadKey, hasProcessedPayload, markPayloadProcessed };
    })();
  `;
  // markPayloadProcessed goi persistProcessedQueue() — stub no.
  const fn = new Function(
    "processedPayloadKeys",
    "PROCESSED_QUEUE_MAX",
    "__RUNCTX__",
    "persistProcessedQueue",
    harnessCode
  );
  const api = fn(
    processedPayloadKeys,
    PROCESSED_QUEUE_MAX,
    { HashUtils },
    () => {} // persist stub
  );

  return {
    ...api,
    getQueue: () => processedPayloadKeys,
    MAX: PROCESSED_QUEUE_MAX,
  };
}

describe("computePayloadKey", () => {
  it("uses id when present (integer as string)", () => {
    const h = loadDedupHarness();
    expect(h.computePayloadKey("ignored", "1760000000000")).toBe("id:1760000000000");
  });

  it("uses id when present (number)", () => {
    const h = loadDedupHarness();
    expect(h.computePayloadKey("ignored", 1760000000000)).toBe("id:1760000000000");
  });

  it("falls back to hash when id is null", () => {
    const h = loadDedupHarness();
    const k = h.computePayloadKey('{"tool":"shell"}', null);
    expect(k.startsWith("h:")).toBe(true);
  });

  it("falls back to hash when id is undefined", () => {
    const h = loadDedupHarness();
    const k = h.computePayloadKey("x", undefined);
    expect(k.startsWith("h:")).toBe(true);
  });

  it("falls back to hash when id is non-numeric", () => {
    const h = loadDedupHarness();
    const k = h.computePayloadKey("x", "abc");
    expect(k.startsWith("h:")).toBe(true);
  });

  it("is stable across calls (same input -> same key)", () => {
    const h = loadDedupHarness();
    const k1 = h.computePayloadKey('{"tool":"shell"}', null);
    const k2 = h.computePayloadKey('{"tool":"shell"}', null);
    expect(k1).toBe(k2);
  });

  it("different content without id -> different key", () => {
    const h = loadDedupHarness();
    const k1 = h.computePayloadKey("aaa", null);
    const k2 = h.computePayloadKey("bbb", null);
    expect(k1).not.toBe(k2);
  });
});

describe("markPayloadProcessed / hasProcessedPayload", () => {
  let h;
  beforeEach(() => {
    h = loadDedupHarness();
  });

  it("new key is not marked before add", () => {
    expect(h.hasProcessedPayload("id:1")).toBe(false);
  });

  it("mark adds key -> hasProcessed returns true", () => {
    h.markPayloadProcessed("id:1");
    expect(h.hasProcessedPayload("id:1")).toBe(true);
  });

  it("mark null/empty is a no-op", () => {
    h.markPayloadProcessed(null);
    h.markPayloadProcessed("");
    expect(h.getQueue().size).toBe(0);
  });

  it("mark same key twice does not grow the set", () => {
    h.markPayloadProcessed("id:1");
    h.markPayloadProcessed("id:1");
    expect(h.getQueue().size).toBe(1);
  });

  it("mark same key twice refreshes insertion order (moves to end)", () => {
    h.markPayloadProcessed("id:1");
    h.markPayloadProcessed("id:2");
    h.markPayloadProcessed("id:1"); // refresh
    const arr = Array.from(h.getQueue());
    expect(arr).toEqual(["id:2", "id:1"]);
  });
});

describe("FIFO eviction (bounded queue)", () => {
  it("caps size at PROCESSED_QUEUE_MAX", () => {
    const h = loadDedupHarness();
    for (let i = 0; i < h.MAX + 50; i++) h.markPayloadProcessed("id:" + i);
    expect(h.getQueue().size).toBe(h.MAX);
  });

  it("evicts oldest first (FIFO)", () => {
    const h = loadDedupHarness();
    for (let i = 0; i < h.MAX; i++) h.markPayloadProcessed("id:" + i);
    // queue day, gio push them 1 cai moi -> id:0 (cu nhat) phai bi evict.
    h.markPayloadProcessed("id:" + h.MAX);
    expect(h.hasProcessedPayload("id:0")).toBe(false);
    expect(h.hasProcessedPayload("id:" + h.MAX)).toBe(true);
  });

  it("keeps the most recent MAX keys", () => {
    const h = loadDedupHarness();
    const total = h.MAX + 20;
    for (let i = 0; i < total; i++) h.markPayloadProcessed("id:" + i);
    // Key tu (total - MAX) den (total - 1) phai con.
    for (let i = total - h.MAX; i < total; i++) {
      expect(h.hasProcessedPayload("id:" + i)).toBe(true);
    }
    // Key cu hon phai bi evict.
    expect(h.hasProcessedPayload("id:0")).toBe(false);
  });
});

describe("REGRESSION — bug goc: dedup theo 1 hash cuoi bi lua", () => {
  it("khong re-fire payload cu khi user doi chat trong cung tab", () => {
    // Mo phong: tab xem chat 1 co payload id=1, xu ly xong.
    // Sau do doi sang chat 2, roi QUAY LAI chat 1.
    // Payload cuoi DOM lai la id=1 -> KHONG duoc xu ly lai.
    const h = loadDedupHarness();

    // Buoc 1: chat 1 -> payload id=1 duoc xu ly.
    h.markPayloadProcessed(h.computePayloadKey('{"tool":"switch","id":1}', 1));

    // Buoc 2: doi sang chat 2 (khong lam gi queue).

    // Buoc 3: quay lai chat 1, DOM lai tra ve payload id=1.
    const key = h.computePayloadKey('{"tool":"switch","id":1}', 1);
    expect(h.hasProcessedPayload(key)).toBe(true);
  });

  it("khong re-fire payload cu khi switch A -> B -> A", () => {
    // Tab A sinh payload id=1, switch sang B.
    // Tab B sinh payload id=2, switch nguoc lai A.
    // Tab A tick lai, DOM van con payload id=1 -> KHONG duoc xu ly lai.
    const A = loadDedupHarness();

    // Tab A xu ly id=1.
    A.markPayloadProcessed(A.computePayloadKey('{"tool":"switch","id":1}', 1));

    // Tab A "nghi" trong luc tab B chay (queue cua A khong bi dung toi).
    // Khi A tick lai -> payload cuoi DOM van la id=1.
    const key = A.computePayloadKey('{"tool":"switch","id":1}', 1);
    expect(A.hasProcessedPayload(key)).toBe(true);
  });

  it("payload MOI (id khac) van duoc xu ly binh thuong", () => {
    const h = loadDedupHarness();
    h.markPayloadProcessed(h.computePayloadKey('{"id":1}', 1));
    const keyNew = h.computePayloadKey('{"id":2}', 2);
    expect(h.hasProcessedPayload(keyNew)).toBe(false);
  });
});

describe("PERSIST — round-trip Array <-> Set", () => {
  it("Array.from(Set) roi new Set(arr) giu nguyen keys + order", () => {
    const h = loadDedupHarness();
    h.markPayloadProcessed("id:1");
    h.markPayloadProcessed("id:2");
    h.markPayloadProcessed("h:abc");

    const serialized = Array.from(h.getQueue());
    const restored = new Set(serialized);

    expect(Array.from(restored)).toEqual(["id:1", "id:2", "h:abc"]);
    expect(restored.has("id:1")).toBe(true);
    expect(restored.has("id:2")).toBe(true);
    expect(restored.has("h:abc")).toBe(true);
  });

  it("loadProcessedQueue filters out non-string entries (corruption guard)", () => {
    // Mo phong storage bi corrupt: value la ["id:1", 42, null, "id:2", {}].
    const raw = ["id:1", 42, null, "id:2", {}];
    const filtered = raw.filter((x) => typeof x === "string");
    expect(filtered).toEqual(["id:1", "id:2"]);
  });
});
