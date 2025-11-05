/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

console.log("📦 GPS patch for ActivityMenu loaded (auto GPS without confirm)");

function sendLocationCommand(command, sync = false) {
    if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
            type: command,         // "START_LOCATION_SERVICE" or "STOP_LOCATION_SERVICE"
            sync: !!sync           // ensure boolean (true/false)
        }));
    } else {
        console.log("⚠️ Not inside React Native WebView, skipping...");
    }
}

// GPS Module Extension
const GPSExtension = {
    async handleGPSTracking(wasCheckedIn) {
        const gpsTracker = window.odoo?.gpsTracker;

        if (!gpsTracker) return;

        const isGpsEnabled = await gpsTracker.isGpsTrackingEnabled();
        console.log("GPS tracking enabled for user:", isGpsEnabled);

        if (isGpsEnabled) {
            if (!wasCheckedIn) {
                console.log("Starting GPS tracking");
                sendLocationCommand("START_LOCATION_SERVICE", false);
            } else {
                console.log("Stopping GPS tracking");
                sendLocationCommand("STOP_LOCATION_SERVICE", true);
            }
        }
    }
};

patch(ActivityMenu.prototype, {
    async signInOut() {
        const wasCheckedIn = this.state.checkedIn;
        console.log("📍 GPS Module - signInOut triggered. Was checked in?", wasCheckedIn);

        // Check if this module should handle the attendance or let others handle it
        if (this._attendanceProcessed) {
            console.log("📍 Attendance already processed by another module, handling GPS only");
            await GPSExtension.handleGPSTracking(wasCheckedIn);
            return;
        }

        // Check if there's another module that will handle attendance
        const hasDeviceDetectionModule = this._hasDeviceDetectionModule ||
            (window.DeviceUtils && typeof window.DeviceUtils.detectLoginType === 'function');

        if (hasDeviceDetectionModule) {
            // Let the device detection module handle the attendance
            console.log("📍 Device detection module present, letting it handle attendance");
            await super.signInOut?.();
            await GPSExtension.handleGPSTracking(wasCheckedIn);
            return;
        }

        // This module will handle the attendance
        this._attendanceProcessed = true;

        return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
                async ({ coords: { latitude, longitude } }) => {
                    try {
                        await this.rpc("/web/hr_attendance/systray_check_in_out", {
                            latitude,
                            longitude,
                        });
                        await this.searchReadEmployee();

                        // Handle GPS tracking
                        await GPSExtension.handleGPSTracking(wasCheckedIn);
                    } catch (error) {
                        console.error("📍 Error in attendance RPC:", error);
                    } finally {
                        // Reset the flag for next time
                        setTimeout(() => {
                            this._attendanceProcessed = false;
                        }, 1000);
                        resolve();
                    }
                },
                async (error) => {
                    console.warn("⚠️ Geolocation error:", error.message);
                    alert("GPS access denied or failed. Attendance is still recorded.");

                    try {
                        await this.rpc("/web/hr_attendance/systray_check_in_out");
                        await this.searchReadEmployee();

                        // Handle GPS tracking for checkout
                        if (wasCheckedIn) {
                            await GPSExtension.handleGPSTracking(wasCheckedIn);
                        }
                    } catch (error) {
                        console.error("📍 Error in attendance RPC (no GPS):", error);
                    } finally {
                        // Reset the flag for next time
                        setTimeout(() => {
                            this._attendanceProcessed = false;
                        }, 1000);
                        resolve();
                    }
                },
                { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
            );
        });
    }
});


///** @odoo-module **/
//
//import { patch } from "@web/core/utils/patch";
//import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
//
//console.log("📦 GPS patch for ActivityMenu loaded (auto GPS without confirm)");
//
//function sendLocationCommand(command, sync = false) {
//    if (window.ReactNativeWebView) {
//        window.ReactNativeWebView.postMessage(JSON.stringify({
//            type: command,         // "START_LOCATION_SERVICE" or "STOP_LOCATION_SERVICE"
//            sync: !!sync           // ensure boolean (true/false)
//        }));
//    } else {
//        console.log("⚠️ Not inside React Native WebView, skipping...");
//    }
//}
//
//patch(ActivityMenu.prototype, {
//    async signInOut() {
//        const gpsTracker = window.odoo?.gpsTracker;
//        const wasCheckedIn = this.state.checkedIn;
//
//        console.log("📍 Patched signInOut triggered. Was checked in?", wasCheckedIn);
//
//        let isGpsEnabled = false;
//        if (gpsTracker) {
//            isGpsEnabled = await gpsTracker.isGpsTrackingEnabled();
//            console.log("GPS tracking enabled for user:", isGpsEnabled);
//        }
//
//        return new Promise((resolve) => {
//            navigator.geolocation.getCurrentPosition(
//                async ({ coords: { latitude, longitude } }) => {
//                    try {
//                        await this.rpc("/web/hr_attendance/systray_check_in_out", {
//                            latitude,
//                            longitude,
//                        });
//                        await this.searchReadEmployee();
//
//                        if (gpsTracker && isGpsEnabled) {
//                            if (!wasCheckedIn) {
//                                console.log("Starting GPS tracking");
//                                sendLocationCommand("START_LOCATION_SERVICE", false);
//                            } else {
//                                console.log("Stopping GPS tracking");
//                                sendLocationCommand("STOP_LOCATION_SERVICE", true);
//                            }
//                        }
//                    } finally {
//                        resolve();
//                    }
//                },
//                async (error) => {
//                    console.warn("⚠️ Geolocation error:", error.message);
//                    alert("GPS access denied or failed. Attendance is still recorded.");
//
//                    try {
//                        await this.rpc("/web/hr_attendance/systray_check_in_out");
//                        await this.searchReadEmployee();
//
//                        if (gpsTracker && wasCheckedIn && isGpsEnabled) {
//                            console.log("Stopping GPS tracking (after error)");
//                            sendLocationCommand("STOP_LOCATION_SERVICE", true);
//                        }
//                    } finally {
//                        resolve();
//                    }
//                },
//                { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
//            );
//        });
//    }
//
//});
