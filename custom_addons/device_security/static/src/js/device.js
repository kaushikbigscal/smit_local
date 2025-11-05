/** @odoo-module **/

//// version final date: 30-07-25

import { WebClient } from "@web/webclient/webclient";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";


// Constants
const STORAGE_KEY = 'odoo_device_uuid';
const MOBILE_BREAKPOINT = 1024;

// Cache variables
let deviceInfoCache = null;
let deviceTypeCache = null;
let isSecurityCheckFailed = false; // Global flag to prevent UI interaction

/**
 * Device UUID Manager
 */
class DeviceUUIDManager {
    static getUUID() {
        try {
            let uuid = localStorage.getItem(STORAGE_KEY);
            if (!uuid) {
                uuid = self.crypto?.randomUUID?.() || this.generateFallbackUUID();
                localStorage.setItem(STORAGE_KEY, uuid);
            }
            return uuid;
        } catch (error) {
            console.warn('localStorage unavailable, using session UUID');
            return this.generateFallbackUUID();
        }
    }

    static generateFallbackUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
}

/**
 * Device Detector
 */
class DeviceDetector {
    static detectLoginType() {
        if (deviceTypeCache) return deviceTypeCache;

        const { userAgent } = navigator;
        const mobilePattern = /mobile|android|iphone|ipad|tablet|blackberry|webos/i;
        const isMobileUA = mobilePattern.test(userAgent);
        const isMobileScreen = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
        const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

        deviceTypeCache = (isMobileUA || (isMobileScreen && isTouchDevice)) ? 'mobile' : 'web';
        return deviceTypeCache;
    }

    static getDetailedDeviceInfo() {
        if (deviceInfoCache) return deviceInfoCache;

        // Try to get from sessionStorage first
        const cachedInfo = sessionStorage.getItem('odoo_device_info');
        if (cachedInfo) {
            deviceInfoCache = JSON.parse(cachedInfo);
            return deviceInfoCache;
        }

        const { userAgent, platform, vendor, language, cookieEnabled, onLine } = navigator;
        const parsedInfo = this.parseUserAgent(userAgent);

        deviceInfoCache = {
            ...parsedInfo,
            platform: platform || 'Unknown',
            vendor: vendor || 'Unknown',
            device_type: this.detectLoginType(),
            screen_resolution: `${screen.width}x${screen.height}`,
            viewport: `${innerWidth}x${innerHeight}`,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            language,
            cookie_enabled: cookieEnabled,
            online: onLine,
            user_agent: userAgent.substring(0, 1000),
        };

        // Store in sessionStorage
        sessionStorage.setItem('odoo_device_info', JSON.stringify(deviceInfoCache));

        return deviceInfoCache;
    }

    static parseUserAgent(userAgent) {
        const patterns = {
            windows: /Windows NT (\d+\.\d+)/,
            macos: /Mac OS X (\d+[._]\d+[._]\d+)/,
            android: /Android (\d+\.\d+)/,
            ios: /OS (\d+_\d+)/,
            chrome: /Chrome\/(\d+\.\d+)/,
            firefox: /Firefox\/(\d+\.\d+)/,
            safari: /Version\/(\d+\.\d+)/,
            edge: /Edg\/(\d+\.\d+)/
        };

        let os = 'Unknown', browser = 'Unknown', device_model = 'Unknown';

        // OS Detection
        if (patterns.windows.test(userAgent)) {
            const match = userAgent.match(patterns.windows);
            os = match ? `Windows ${match[1]}` : 'Windows';
        } else if (patterns.macos.test(userAgent)) {
            const match = userAgent.match(patterns.macos);
            os = match ? `macOS ${match[1].replace(/_/g, '.')}` : 'macOS';
        } else if (patterns.android.test(userAgent)) {
            const match = userAgent.match(patterns.android);
            os = match ? `Android ${match[1]}` : 'Android';
            const deviceMatch = userAgent.match(/; ([^;]+) Build\//);
            device_model = deviceMatch ? deviceMatch[1] : 'Android Device';
        } else if (patterns.ios.test(userAgent)) {
            const match = userAgent.match(patterns.ios);
            os = match ? `iOS ${match[1].replace(/_/g, '.')}` : 'iOS';
            device_model = userAgent.includes('iPad') ? 'iPad' : 'iPhone';
        } else if (userAgent.includes('Linux')) {
            os = 'Linux';
        }

        // Browser Detection
        if (patterns.chrome.test(userAgent) && !userAgent.includes('Edg')) {
            const match = userAgent.match(patterns.chrome);
            browser = match ? `Chrome ${match[1]}` : 'Chrome';
        } else if (patterns.firefox.test(userAgent)) {
            const match = userAgent.match(patterns.firefox);
            browser = match ? `Firefox ${match[1]}` : 'Firefox';
        } else if (patterns.safari.test(userAgent) && !userAgent.includes('Chrome')) {
            const match = userAgent.match(patterns.safari);
            browser = match ? `Safari ${match[1]}` : 'Safari';
        } else if (patterns.edge.test(userAgent)) {
            const match = userAgent.match(patterns.edge);
            browser = match ? `Edge ${match[1]}` : 'Edge';
        }

        return { os, browser, device_model };
    }

    static clearCache() {
        deviceInfoCache = null;
        deviceTypeCache = null;
    }

}

/**
 * Bulletproof Error Dialog that cannot be dismissed
 */
class BulletproofErrorDialog {
    static activeDialog = null;
    static logoutTimer = null;

    static show(message, title = "Device Registration Failed") {
        // Set global flag to prevent any UI interaction
        isSecurityCheckFailed = true;

        // Clear any existing dialog and timer
        this.close();

        // Block all user interactions immediately
        this.blockAllInteractions();

        // Show the error dialog
        this.createUnDismissibleDialog(message, title);

        // Force logout after 5 seconds regardless of user action
        this.logoutTimer = setTimeout(() => {
            this.forceLogout();
        }, 5000);
    }

    static blockAllInteractions() {
        // Create full-screen overlay to block all clicks
        const blocker = document.createElement('div');
        blocker.id = 'security-blocker';
        blocker.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            z-index: 999999;
            cursor: not-allowed;
        `;

        // Block all events
        blocker.addEventListener('click', (e) => e.stopPropagation(), true);
        blocker.addEventListener('keydown', (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, true);

        document.body.appendChild(blocker);

        // Disable all form elements
        document.querySelectorAll('input, button, select, textarea, a').forEach(el => {
            el.disabled = true;
            el.style.pointerEvents = 'none';
        });
    }

    static createUnDismissibleDialog(message, title) {
        // Remove any existing dialog
        const existingDialog = document.getElementById('bulletproof-security-dialog');
        if (existingDialog) {
            existingDialog.remove();
        }

        const dialog = document.createElement('div');
        dialog.id = 'bulletproof-security-dialog';
        dialog.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            border: 3px solid #dc3545;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            max-width: 500px;
            width: 90%;
            z-index: 9999999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;

        dialog.innerHTML = `
            <div style="background: #dc3545; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                <h3 style="margin: 0; color: white; font-size: 18px; font-weight: 600;">
                    ${title}
                </h3>
            </div>
            <div style="padding: 25px; font-size: 16px; line-height: 1.6; color: #333;">
                <p style="margin: 0 0 20px 0;">${message}</p>
                <p style="margin: 0; font-weight: bold; color: #dc3545;">
                    You will be automatically logged out in <span id="countdown">5</span> seconds...
                </p>
            </div>
            <div style="padding: 20px; text-align: center; border-top: 1px solid #eee;">
                <button id="logout-now-btn" style="
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 5px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.2s;
                ">
                    Logout Now
                </button>
            </div>
        `;

        // Add pulsing animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                from { transform: translate(-50%, -50%) scale(1); }
                to { transform: translate(-50%, -50%) scale(1.02); }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(dialog);

        // Start countdown
        this.startCountdown();

        // Add logout button handler
        document.getElementById('logout-now-btn').onclick = () => {
            this.forceLogout();
        };

        // Prevent dialog from being removed or hidden
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    mutation.removedNodes.forEach((node) => {
                        if (node.id === 'bulletproof-security-dialog') {
                            // If dialog is removed, recreate it immediately
                            setTimeout(() => {
                                if (isSecurityCheckFailed) {
                                    this.createUnDismissibleDialog(message, title);
                                }
                            }, 10);
                        }
                    });
                }
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });
        this.activeDialog = { dialog, observer };
    }

    static startCountdown() {
        let timeLeft = 5;
        const countdownElement = document.getElementById('countdown');

        const countdownInterval = setInterval(() => {
            timeLeft--;
            if (countdownElement) {
                countdownElement.textContent = timeLeft;
            }

            if (timeLeft <= 0) {
                clearInterval(countdownInterval);
                this.forceLogout();
            }
        }, 1000);
    }

    static forceLogout() {
        // Clear timers
        if (this.logoutTimer) {
            clearTimeout(this.logoutTimer);
            this.logoutTimer = null;
        }

        // Show logout message
        const blocker = document.getElementById('security-blocker');
        if (blocker) {
            blocker.innerHTML = `
                <div style="
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    text-align: center;
                    font-size: 18px;
                    font-weight: bold;
                    color: #dc3545;
                ">
                    Logging out for security reasons...
                </div>
            `;
        }

        // Force logout immediately - try multiple methods
        this.attemptLogout();
    }

    static attemptLogout() {
        // Method 1: Standard logout URL
        window.location.replace('/web/session/logout?redirect=/web/login');

        // Method 2: Fallback after 2 seconds
        setTimeout(() => {
            window.location.href = '/web/session/logout';
        }, 2000);

        // Method 3: Hard refresh fallback after 4 seconds
        setTimeout(() => {
            window.location.reload(true);
        }, 4000);

        // Method 4: Last resort - close window after 6 seconds
        setTimeout(() => {
            try {
                window.close();
            } catch (e) {
                // If can't close, redirect to login
                window.location.replace('/web/login');
            }
        }, 6000);
    }

    static close() {
        if (this.activeDialog) {
            this.activeDialog.observer?.disconnect();
            this.activeDialog.dialog?.remove();
            this.activeDialog = null;
        }

        if (this.logoutTimer) {
            clearTimeout(this.logoutTimer);
            this.logoutTimer = null;
        }

        // Remove blocker
        const blocker = document.getElementById('security-blocker');
        if (blocker) {
            blocker.remove();
        }

        isSecurityCheckFailed = false;
    }
}

/**
 * Device Security Service
 */
export const deviceSecurityService = {
    dependencies: ["rpc"],

    start(env, { rpc }) {
        return {
            async registerDevice(loginType = 'web') {
                // Prevent multiple registration attempts
                if (this._registering || isSecurityCheckFailed) {
                    return this._registrationPromise || Promise.resolve(false);
                }

                this._registering = true;
                this._registrationPromise = this._performRegistration(rpc, loginType);

                try {
                    return await this._registrationPromise;
                } finally {
                    this._registering = false;
                }
            },

//            async _performRegistration(rpc, loginType) {
//                const uuid = DeviceUUIDManager.getUUID();
//                const deviceInfo = DeviceDetector.getDetailedDeviceInfo();
//
//                try {
//                    const result = await rpc('/device/register', {
//                        device_uuid: uuid,
//                        login_type: loginType,
//                        device_info: deviceInfo
//                    });
//
//                    // Log success but don't show popup to avoid interruption
//                    if (result.message?.includes('first login')) {
//                        console.log('✅ Device registered successfully for first login after reset');
//                    }
//
//                    return true;
//                } catch (err) {
//                    const errorMsg = this._extractErrorMessage(err);
//
//                    // Show bulletproof error dialog
//                    BulletproofErrorDialog.show(errorMsg, 'Device Registration Failed');
//
//                    return false;
//                }
//            },

            async _performRegistration(rpc, loginType) {
                const uuid = DeviceUUIDManager.getUUID();
                const deviceInfo = DeviceDetector.getDetailedDeviceInfo();

                let retries = 0;
                while (retries < 2) {
                    try {
                        const result = await rpc('/device/register', {
                            device_uuid: uuid,
                            login_type: loginType,
                            device_info: deviceInfo
                        });

                        if (result.message?.includes('first login')) {
                            console.log('✅ Device registered successfully for first login after reset');
                        }

                        return true;
                    } catch (err) {
                        retries++;

                        // 🟢 If it looks like Odoo update/session expired, skip hard block
                        const errorMsg = this._extractErrorMessage(err);
                        if (errorMsg.includes("Session expired") || errorMsg.includes("Invalid CSRF") || errorMsg.includes("404") || errorMsg.includes("Not Found")) {
                            console.warn("Odoo restart/session expired detected, skipping device lock");
                            return false;  // just force user to re-login normally
                        }

                        // Retry once after short delay
                        if (retries < 2) {
                            await new Promise(r => setTimeout(r, 1000));
                            continue;
                        }

                        // 🛑 Real device error after retry
                        BulletproofErrorDialog.show(errorMsg, 'Device Registration Failed');
                        return false;
                    }
                }
            },

            _extractErrorMessage(err) {
                return err?.message?.data?.message ||
                       err?.data?.message ||
                       (typeof err === 'string' ? err :
                        'Access denied: You have already logged in from another device. Please contact your administrator for device registration.');
            },

            getDeviceInfo() {
                return {
                    uuid: DeviceUUIDManager.getUUID(),
                    type: DeviceDetector.detectLoginType(),
                    ...DeviceDetector.getDetailedDeviceInfo()
                };
            },

            clearCache() {
                DeviceDetector.clearCache();
            }
        };
    }
};

// Register the service
registry.category("services").add("device_security", deviceSecurityService);

/**
 * WebClient patch with bulletproof security
 */
patch(WebClient.prototype, {
    async setup() {
        await super.setup();

        // Run device security check for authenticated users
        if (session.uid) {
            this._runDeviceSecurityCheck();
        }
    },

    async _runDeviceSecurityCheck() {
        try {
            // Immediate check - no delay to prevent bypass
            const deviceSecurity = this.env.services.device_security;
            const loginType = DeviceDetector.detectLoginType();

            const result = await deviceSecurity.registerDevice(loginType);

            // If registration failed, the bulletproof dialog is already shown
            if (!result) {
                console.error('Device security check failed - user will be logged out');
            }
        } catch (error) {
            console.error('Device security check error:', error);
            // Show error dialog even for unexpected errors
            BulletproofErrorDialog.show(
                'A security error occurred. You will be logged out for safety.',
                'Security Error'
            );
        }
    },
});
