/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

const category = registry.category("user_menuitems");
const originalFactory = category.get("log_out");

function patchedLogoutFactory(env) {
    const original = originalFactory(env);

    return {
        ...original,

        callback: async () => {
            let gpsTrackingEnabled = false;

            // --- STEP 1: Check user setting safely ---
            try {
                const result = await env.services.orm.read(
                    "res.users",
                    [env.services.user.userId],
                    ["enable_gps_tracking"]
                );
                gpsTrackingEnabled = !!result?.[0]?.enable_gps_tracking;
            } catch (e) {
                console.warn("Field enable_gps_tracking missing. Skipping.");
            }

            // --- STEP 2: If not a mobile app or setting disabled → normal logout ---
            if (!window.ReactNativeWebView || !gpsTrackingEnabled) {
                browser.location.href = "/web/session/logout";
                return;
            }

            // --- STEP 3: Request confirmation from native ---
            window.ReactNativeWebView.postMessage(
                JSON.stringify({ type: "REQUEST_LOGOUT_CONFIRMATION" })
            );

            let responded = false;
            let timeout;

            // --- STEP 4: Robust message handler ---
            const listener = (event) => {
                let raw = event?.data;

                // Nothing received
                if (raw == null) {
                    console.warn("Received null/undefined message from WebView");
                    return;
                }

                let data = raw;

                // Handle string payloads (Android usually)
                if (typeof raw === "string") {
                    try {
                        data = JSON.parse(raw);
                    } catch (err) {
                        console.warn("Invalid WebView string payload:", raw);
                        return;
                    }
                }

                // Handle object payloads (iOS + newer RN WebViews)
                if (typeof data !== "object") {
                    console.warn("Unexpected payload type:", data);
                    return;
                }

                // --- STEP 5: Process logout confirmation ---
                if (data.type === "LOGOUT_CONFIRMATION_RESPONSE") {
                    responded = true;
                    clearTimeout(timeout);

                    window.removeEventListener("message", listener);

                    if (data.approved === true) {
                        browser.location.href = "/web/session/logout";
                    } else {
                        alert("Logout cancelled by app.");
                    }
                }
            };

            // Attach listener only once
            window.addEventListener("message", listener);

            // --- STEP 6: Fallback timeout to avoid stuck UI ---
            timeout = setTimeout(() => {
                if (!responded) {
                    window.removeEventListener("message", listener);
                    alert("App did not respond. Logout cancelled.");
                }
            }, 20000);
        },
    };
}

category.add("log_out", patchedLogoutFactory, { force: true });






///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { browser } from "@web/core/browser/browser";
//
//const category = registry.category("user_menuitems");
//const originalFactory = category.get("log_out");
//
//function patchedLogoutFactory(env) {
//    const original = originalFactory(env);
//
//    return {
//        ...original,
//
//        callback: async () => {
//
//            let gpsTrackingEnabled = false;
//
//            try {
//                const result = await env.services.orm.read(
//                    "res.users",
//                    [env.services.user.userId],
//                    ["enable_gps_tracking"]
//                );
//                gpsTrackingEnabled = result?.[0]?.enable_gps_tracking === true;
//            } catch (e) {
//                console.warn("Field enable_gps_tracking missing. Skipping.");
//            }
//
//            // NOT in native OR GPS disabled → normal logout
//            if (!window.ReactNativeWebView || !gpsTrackingEnabled) {
//                browser.location.href = "/web/session/logout";
//                return;
//            }
//
//            // Send logout request to native
//            window.ReactNativeWebView.postMessage(
//                JSON.stringify({ type: "REQUEST_LOGOUT_CONFIRMATION" })
//            );
//
//            let responded = false;
//
//            // 1️⃣ Define listener first
//            const listener = (event) => {
//                try {
//                    let raw = event.data;
//                    let data = raw;
//
//                    if (typeof raw === "string") {
//                        try {
//                            data = JSON.parse(raw);
//                        } catch (err) {
//                            alert("Invalid string received:\n" + raw);
//                            return;
//                        }
//                    } else if (typeof raw !== "object") {
//                        alert("Unknown data type received:\n" + String(raw));
//                        return;
//                    }
//                    // Debug view
//                    alert("Parsed Data:\n" + JSON.stringify(data, null, 2));
//
//                    if (data.type === "LOGOUT_CONFIRMATION_RESPONSE") {
//                        responded = true;
//                        clearTimeout(timeout);
//
//                        if (data.approved) {
//                            browser.location.href = "/web/session/logout";
//                        } else {
//                            alert("Logout cancelled by app.");
//                        }
//
//                        window.removeEventListener("message", listener);
//                    }
//                } catch (err) {
//                    console.warn("Invalid RN WebView data", err);
//                    alert("Error: " + err.message + "\n\n" + err.stack);
//                }
//            };
//
//            // 2️⃣ Attach listener
//            window.addEventListener("message", listener);
//
//            // 3️⃣ NOW start the timeout
//            const timeout = setTimeout(() => {
//                if (!responded) {
//                    alert("App did not respond. Logout cancelled.");
//                    window.removeEventListener("message", listener);
//                }
//            }, 20000);
//        },
//    };
//}
//
//category.add("log_out", patchedLogoutFactory, { force: true });
