import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createRuntimeUrls } from "../src/api.js";
import { clientPage } from "../src/pagination.js";

test("downstream runtime retains host-neutral URL configuration", () => {
    const urls = createRuntimeUrls({ apiBase: "/host/tui", bootstrapUrl: false });
    assert.equal(urls.catalog(), "/host/tui/catalog/");
    assert.equal(urls.bootstrap("home"), "");
});

test("downstream runtime paginates large local datasets", () => {
    const result = clientPage(Array.from({ length: 101 }, (_, index) => index), 2, 100);
    assert.deepEqual(result.rows, [100]);
    assert.equal(result.pager.total_pages, 2);
});

test("downstream generic bundle rejects upstream business leakage", () => {
    const bundles = [
        "../../reference/static/js/agomtui-runtime-core.js",
        "../../reference/static/js/tui-workbench.js",
    ].map((relative) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8"));
    for (const forbidden of [
        "operator.governance.",
        "operator.home.",
        "ai-ops.providers",
        "capability-router.mcp-center",
        "api-library.runtime",
        "/api/operator/",
        "Terminal/TUI 运行面状态",
    ]) {
        assert.equal(bundles.some((bundle) => bundle.includes(forbidden)), false, `business identifier leaked: ${forbidden}`);
    }
});
