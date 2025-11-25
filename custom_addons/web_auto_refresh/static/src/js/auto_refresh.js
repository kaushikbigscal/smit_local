/** @odoo-module **/

import { registry } from "@web/core/registry";

let refreshTimeout;

console.log("[Auto Refresh] JS module loaded — waiting for Odoo startup...");

async function setupAutoRefresh(rpc) {
    console.log("[Auto Refresh] setupAutoRefresh() called — starting logic");

    try {
        // ✅ Use custom controller instead of ir.config_parameter RPC
        const result = await rpc("/web_auto_refresh/config", {});
        console.log("[Auto Refresh] Response:", result);

        if (result.error) {
            console.warn("[Auto Refresh] ❌ Backend error:", result.error);
            return;
        }

        if (!result.enabled) {
            console.log("[Auto Refresh] Disabled — skipping auto reload.");
            clearTimeout(refreshTimeout);
            return;
        }

        const refreshTime = parseInt(result.interval || 0);
        if (isNaN(refreshTime) || refreshTime <= 0) {
            console.log("[Auto Refresh] Invalid or zero interval — skipping.");
            return;
        }

        console.log(`[Auto Refresh] ✅ Enabled — page will reload every ${refreshTime} seconds.`);
        clearTimeout(refreshTimeout);
        refreshTimeout = setTimeout(() => {
            console.log("[Auto Refresh] ⟳ Refresh triggered — reloading page...");
            window.location.reload();
        }, refreshTime * 1000);
    } catch (error) {
        console.warn("[Auto Refresh] ❌ setupAutoRefresh() failed:", error);
    }
}

// ✅ Register as a startup service
registry.category("services").add("auto_refresh_service", {
    start(env) {
        console.log("[Auto Refresh] ✅ Service hook triggered — initializing auto refresh...");
        const rpc = env.services.rpc;
        if (!rpc) {
            console.error("[Auto Refresh] ❌ RPC service not found!");
            return;
        }
        setupAutoRefresh(rpc);
    },
});
