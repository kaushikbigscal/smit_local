/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";


// Cache for values
let gpsCache = {
    not_allow: null,
    gpsRequired: null,
};

// Listen for messages from Native
window.addEventListener("message", async (event) => {
    try {
        let data = event.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }

        if (data.type === "USER_NOT_ALLOW") {
            gpsCache.not_allow = data.flag;

            if (gpsCache.not_allow === true) {
                // ✅ Only create attendance if GPS_REQUIRED was false
                if (gpsCache.gpsRequired === false && window.odoo) {
                    try {

                        // ✅ Use the same endpoint as the systray button
                        const response = await fetch("/web/hr_attendance/systray_check_in_out", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                jsonrpc: "2.0",
                                method: "call",
                                params: {},
                                id: new Date().getTime(),
                            }),
                        });

                        const result = await response.json();

                        if (result.error) {
                            throw new Error(result.error.data?.message || result.error.message || "Unknown error");
                        }

                    } catch (err) {
                        console.error("Failed to create attendance:", err);

//                        // More detailed error message
//                        let errorMsg = "Failed to create attendance";
//                        if (err.message) {
//                            errorMsg += `: ${err.message}`;
//                        } else if (err.data?.message) {
//                            errorMsg += `: ${err.data.message}`;
//                        }
//
//                        alert(`${errorMsg}`);
                    }
                } else {
                    alert("For Attendance Day-in/out you have to allow GPS service.");
                }
            }
        }
    } catch (err) {
        console.warn("⚠️ Failed to parse message from RN:", event.data, err);
    }
});

const originalSearchReadEmployee = ActivityMenu.prototype.searchReadEmployee;

patch(ActivityMenu.prototype, {
    async searchReadEmployee(...args) {
        await originalSearchReadEmployee.apply(this, args);


        let gpsRequired = false;

        try {
            // Single RPC call to get GPS flag
            const result = await this.rpc("/web/dataset/call_kw/hr.attendance", {
                model: "hr.attendance",
                method: "get_gps_required_flag",
                args: [],
                kwargs: {},
            });

            gpsRequired = result.gps_required;
            gpsCache.gpsRequired = gpsRequired;

        } catch (e) {
            gpsRequired = false;
            gpsCache.gpsRequired = gpsRequired;
        }

        // Send flag to React Native WebView
        if (window.ReactNativeWebView) {
            window.ReactNativeWebView.postMessage(JSON.stringify({
                type: "GPS_REQUIRED",
                flag: gpsRequired,
            }));
        } else {
            console.log("⚠️ Not inside App, gps_required flag:", gpsRequired);
        }
    },
});
