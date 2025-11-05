/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

// Device Detection Utilities
const DeviceUtils = {
    detectLoginType() {
        const userAgent = navigator.userAgent.toLowerCase();
        const mobileKeywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet', 'blackberry', 'webos'];
        const isMobileUA = mobileKeywords.some(keyword => userAgent.includes(keyword));
        const isMobileScreen = window.matchMedia("(max-width: 1024px)").matches;
        const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        return (isMobileUA || (isMobileScreen && isTouchDevice)) ? 'mobile' : 'web';
    },

    isMobileDevice() {
        return this.detectLoginType() === 'mobile';
    },

    isIosApp() {
        return /iPad|iPhone|iPod/.test(navigator.userAgent) &&
               (window.webkit?.messageHandlers || window.ReactNativeWebView);
    }
};

// Make DeviceUtils available globally for coordination
window.DeviceUtils = DeviceUtils;

patch(ActivityMenu.prototype, {
    async initAttendanceState(...args) {
        // Call the original or previously patched method
        await super.initAttendanceState?.(...args);

        if (this.employee && this.employee.id) {
            try {
                const userResult = await this.rpc("/web/dataset/call_kw", {
                    model: "res.users",
                    method: "read",
                    args: [[this.env.services.user.userId], ["attendance_capture_mode"]],
                    kwargs: {}
                });

                const mode = userResult[0]?.attendance_capture_mode || 'mobile-web';
                const isWeb = mode === "web" || mode === "mobile-web";
                const isMobile = mode === "mobile" || mode === "mobile-web";
                const isBiometric = mode === "biometric";

                const isMobileDeviceNow = DeviceUtils.isMobileDevice();
                const currentLoginType = DeviceUtils.detectLoginType();

                console.log(`Current device detection: ${currentLoginType}, isMobileDeviceNow: ${isMobileDeviceNow}`);
                console.log(`Attendance capture mode: ${mode}`);

                if (isBiometric) {
                    this.state.isDisplayed = false;
                } else if (isWeb && !isMobileDeviceNow) {
                    this.state.isDisplayed = true;
                } else if (isMobile && isMobileDeviceNow) {
                    this.state.isDisplayed = true;
                } else {
                    this.state.isDisplayed = false;
                }
            } catch (error) {
                console.error("Error getting attendance capture mode:", error);
                this.state.isDisplayed = true;
            }
        }
    },

    async signInOut(...args) {
        console.log("Hello from device detection module sign-in/out");
        console.log(`Device type detected: ${DeviceUtils.detectLoginType()}`);

        // Mark that this module is present
        this._hasDeviceDetectionModule = true;

        // Check if GPS module already processed attendance
        if (this._attendanceProcessed) {
            console.log("📱 Attendance already processed by GPS module, skipping");
            return;
        }

        // Call the GPS module's method first if it exists
        const gpsModuleExists = window.odoo?.gpsTracker ||
            (typeof sendLocationCommand === 'function');

        if (gpsModuleExists) {
            console.log("📱 GPS module detected, letting it handle attendance");
            await super.signInOut?.(...args);
            return;
        }

        // This module will handle attendance (GPS module not present)
        console.log("📱 No GPS module, handling attendance with device detection");
        this._attendanceProcessed = true;

        try {
            if (!DeviceUtils.isIosApp()) {
                return new Promise((resolve) => {
                    navigator.geolocation.getCurrentPosition(
                        async ({ coords: { latitude, longitude } }) => {
                            try {
                                await this.rpc("/web/hr_attendance/systray_check_in_out", {
                                    latitude,
                                    longitude
                                });
                                await this.searchReadEmployee();
                            } catch (error) {
                                console.error("📱 Error in attendance RPC (with location):", error);
                            } finally {
                                // Reset the flag for next time
                                setTimeout(() => {
                                    this._attendanceProcessed = false;
                                }, 1000);
                                resolve();
                            }
                        },
                        async () => {
                            try {
                                await this.rpc("/web/hr_attendance/systray_check_in_out");
                                await this.searchReadEmployee();
                            } catch (error) {
                                console.error("📱 Error in attendance RPC (no location):", error);
                            } finally {
                                // Reset the flag for next time
                                setTimeout(() => {
                                    this._attendanceProcessed = false;
                                }, 1000);
                                resolve();
                            }
                        },
                        { enableHighAccuracy: true }
                    );
                });
            } else {
                await this.rpc("/web/hr_attendance/systray_check_in_out");
                await this.searchReadEmployee();
            }
        } finally {
            // Reset the flag for next time
            setTimeout(() => {
                this._attendanceProcessed = false;
            }, 1000);
        }
    }
});


///** @odoo-module **/
//
//import { patch } from "@web/core/utils/patch";
//import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
//
//// Keep reference to the original methods before patch
//const originalSearchReadEmployee = ActivityMenu.prototype.searchReadEmployee;
//const originalSignInOut = ActivityMenu.prototype.signInOut;
//
//function detectLoginType() {
//    const userAgent = navigator.userAgent.toLowerCase();
//    const mobileKeywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet', 'blackberry', 'webos'];
//    const isMobileUA = mobileKeywords.some(keyword => userAgent.includes(keyword));
//    const isMobileScreen = window.matchMedia("(max-width: 1024px)").matches;
//    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
//    return (isMobileUA || (isMobileScreen && isTouchDevice)) ? 'mobile' : 'web';
//}
//
//function isMobileDevice() {
//    return detectLoginType() === 'mobile';
//}
//
//function isIosApp() {
//    return /iPad|iPhone|iPod/.test(navigator.userAgent) &&
//           (window.webkit?.messageHandlers || window.ReactNativeWebView);
//}
//
//const superSearchReadEmployee = ActivityMenu.prototype.searchReadEmployee;
//const superSignInOut = ActivityMenu.prototype.signInOut;
//
//patch(ActivityMenu.prototype, {
//    async searchReadEmployee(...args) {
//        if (superSearchReadEmployee) {
//            await superSearchReadEmployee.apply(this, args);  // call original/previous
//        }
//
//        if (this.employee && this.employee.id) {
//            try {
//                const userResult = await this.rpc("/web/dataset/call_kw", {
//                    model: "res.users",
//                    method: "read",
//                    args: [[this.env.services.user.userId], ["attendance_capture_mode"]],
//                    kwargs: {}
//                });
//
//                const mode = userResult[0]?.attendance_capture_mode || 'mobile-web';
//                const isWeb = mode === "web" || mode === "mobile-web";
//                const isMobile = mode === "mobile" || mode === "mobile-web";
//                const isBiometric = mode === "biometric";
//
//                const isMobileDeviceNow = isMobileDevice();
//                const currentLoginType = detectLoginType();
//
//                console.log(`Current device detection: ${currentLoginType}, isMobileDeviceNow: ${isMobileDeviceNow}`);
//                console.log(`Attendance capture mode: ${mode}`);
//
//                if (isBiometric) {
//                    this.state.isDisplayed = false;
//                } else if (isWeb && !isMobileDeviceNow) {
//                    this.state.isDisplayed = true;
//                } else if (isMobile && isMobileDeviceNow) {
//                    this.state.isDisplayed = true;
//                } else {
//                    this.state.isDisplayed = false;
//                }
//            } catch (error) {
//                console.error("Error getting attendance capture mode:", error);
//                this.state.isDisplayed = true;
//            }
//        }
//    },
//
//    async signInOut(...args) {
//        if (superSignInOut) {
//            await superSignInOut.apply(this, args);  // call original/previous
//        }
//
//        console.log("Hello from custom sign-in/out in custom module");
//        console.log(`Device type detected: ${detectLoginType()}`);
//
//        if (!isIosApp()) {
//            navigator.geolocation.getCurrentPosition(
//                async ({ coords: { latitude, longitude } }) => {
//                    await this.rpc("/web/hr_attendance/systray_check_in_out", { latitude, longitude });
//                    await this.searchReadEmployee();
//                },
//                async () => {
//                    await this.rpc("/web/hr_attendance/systray_check_in_out");
//                    await this.searchReadEmployee();
//                },
//                { enableHighAccuracy: true }
//            );
//        } else {
//            await this.rpc("/web/hr_attendance/systray_check_in_out");
//            await this.searchReadEmployee();
//        }
//    }
//});
