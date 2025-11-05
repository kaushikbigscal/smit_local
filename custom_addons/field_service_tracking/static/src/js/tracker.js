/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";

let db = null;
let gpsIntervalId = null;
let syncIntervalId = null;
let trackingStartTime = null;
let currentTrackingSession = null;
let lastKnownPosition = null; // Track last position to avoid duplicates

// Configuration for location filtering
const LOCATION_CONFIG = {
    MIN_DISTANCE_METERS: 10, // Minimum distance to consider as movement
    MIN_TIME_SECONDS: 30,    // Minimum time between same location points
    MAX_ACCURACY_METERS: 50  // Maximum GPS accuracy to accept
};

async function getCurrentEmployeeData() {
    try {
        const res = await jsonrpc("/live/gps/get_employee_id", {});
        return res || {};
    } catch (error) {
        console.error("❌ Failed to fetch employee/attendance ID:", error);
        return {};
    }
}



async function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open("odoo_gps_tracker", 1);
        req.onerror = () => reject(req.error);
        req.onsuccess = () => {
            db = req.result;
            resolve(db);
        };
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains("locations")) {
                db.createObjectStore("locations", { keyPath: "timestamp" });
            }
        };
    });
}

// Calculate distance between two points using Haversine formula
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // Earth's radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c; // Distance in meters
}

// Check if location should be saved based on movement and time
function shouldSaveLocation(lat, lon, accuracy, timestamp) {
    // Always save the first location
    if (!lastKnownPosition) {
        return true;
    }

    // Reject low accuracy readings
    if (accuracy > LOCATION_CONFIG.MAX_ACCURACY_METERS) {
        console.log(`🎯 Rejected low accuracy GPS: ${accuracy}m`);
        return false;
    }

    const distance = calculateDistance(
        lastKnownPosition.lat,
        lastKnownPosition.lon,
        lat,
        lon
    );

    const timeDiff = (new Date(timestamp) - new Date(lastKnownPosition.timestamp)) / 1000;

    console.log(`📏 Distance: ${distance.toFixed(2)}m, Time: ${timeDiff.toFixed(0)}s, Accuracy: ${accuracy}m`);

    // Save if moved significantly OR enough time has passed at same location
    if (distance >= LOCATION_CONFIG.MIN_DISTANCE_METERS) {
        console.log("✅ Significant movement detected");
        return true;
    }

    if (timeDiff >= LOCATION_CONFIG.MIN_TIME_SECONDS) {
        console.log("✅ Time threshold reached at same location");
        return true;
    }

    console.log("⏭️ Skipping - insufficient movement/time");
    return false;
}

function saveToLocal(lat, lon, employeeId, attendanceId, accuracy, taskId = null, trackingType = "route_point") {
    if (!db) {
        console.error("❌ Database not initialized");
        return;
    }

    const timestamp = new Date().toISOString();

    // Check if we should save this location
    if (!shouldSaveLocation(lat, lon, accuracy, timestamp)) {
        return Promise.resolve(); // Skip saving
    }

    const tx = db.transaction("locations", "readwrite");
    const store = tx.objectStore("locations");
    const item = {
        timestamp,
        latitude: lat,
        longitude: lon,
        employee_id: employeeId,
        attendance_id: attendanceId,
        tracking_type: trackingType,
        accuracy: accuracy,
        synced: false,
    };

    store.put(item);
    console.log("📍 Saved locally:", item);

    // Update last known position
    lastKnownPosition = {
        lat,
        lon,
        timestamp,
        accuracy
    };

    return tx.complete;
}

async function syncWithServer() {
    if (!db) await openDB();

    const tx = db.transaction("locations", "readwrite");
    const store = tx.objectStore("locations");
    const unsynced = [];

    await new Promise((resolve) => {
        store.openCursor().onsuccess = function (event) {
            const cursor = event.target.result;
            if (cursor) {
                const item = cursor.value;
                const itemTime = new Date(item.timestamp);

                if (!item.synced && (!trackingStartTime || itemTime >= trackingStartTime)) {
                    unsynced.push({ key: cursor.key, data: item });
                }
                cursor.continue();
            } else {
                resolve();
            }
        };
    });

    console.log(`🔄 Syncing ${unsynced.length} unsynced items`);

    for (const item of unsynced) {
        try {
            const res = await fetch("/live/gps/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: item.data,
                }),
            });

            const response = await res.json();

            if (response.result?.status === "ok" || response.result?.status === "duplicate") {
                const updateTx = db.transaction("locations", "readwrite");
                const updateStore = updateTx.objectStore("locations");
                item.data.synced = true;
                updateStore.put(item.data);
                console.log("✅ Synced:", item.data);
            } else {
                console.warn("⚠️ Unexpected response:", response);
            }
        } catch (e) {
            console.warn("❌ Sync error (maybe offline):", e);
        }
    }
}

// 🧠 Exported global tracker object
window.odoo = window.odoo || {};
window.odoo.gpsTracker = {
    startGPSTracking: async function (employeeId = null, attendanceId = null, taskId = null, trackingType = "route_point") {
        try {
            const empData = await getCurrentEmployeeData();

/////////////////////////////////////////////////////////////////////////////////////

            // Handle the new response structure with GPS tracking check
            if (empData.status === "disabled") {
                console.log("GPS tracking is disabled for this user");
                return false;
            }

            if (empData.status === "error") {
                console.error("Error getting employee data:", empData.error);
                return false;
            }

////////////////////////////////////////////////////////////////////////////////////
            employeeId = employeeId || empData.employee_id;
            attendanceId = attendanceId || empData.attendance_id;

            if (!employeeId) {
                console.error("❌ Required employee or attendance ID missing.");
                return false;
            }

            await openDB();

            currentTrackingSession = {
                employeeId,
                attendanceId,
                taskId,
                trackingType,
                startTime: new Date()
            };

            trackingStartTime = new Date();
            lastKnownPosition = null; // Reset position tracking

            // Clear previous intervals
            if (gpsIntervalId) clearInterval(gpsIntervalId);
            if (syncIntervalId) clearInterval(syncIntervalId);

            // Start 10s GPS collection with enhanced filtering
            gpsIntervalId = setInterval(() => {
                navigator.geolocation.getCurrentPosition(
                    async (pos) => {
                        const lat = pos.coords.latitude;
                        const lon = pos.coords.longitude;
                        const accuracy = pos.coords.accuracy;

                        console.log("📡 GPS:", lat, lon, `accuracy: ${accuracy}m`);
                        await saveToLocal(lat, lon, employeeId, attendanceId, accuracy, taskId, trackingType);
                    },
                    (err) => {
                        console.error("❌ GPS Error:", err.message);
                    },
                    {
                        enableHighAccuracy: true,
                        maximumAge: 5000, // Allow 5s old readings
                        timeout: 10000,
                    }
                );
            }, 10000);

            // Start 30s sync interval
            syncIntervalId = setInterval(async () => {
                await syncWithServer();
            }, 30000);

            console.log("▶️ Started GPS tracking with smart location filtering");
            console.log("📊 Filter config:", LOCATION_CONFIG);

            // On startGPSTracking
            localStorage.setItem("gps_session_active", "true");

            return true;

        } catch (error) {
            console.error("❌ Failed to start GPS tracking:", error);
            return false;
        }
    },

    stopGPSTracking: async function () {
        try {
            if (gpsIntervalId) clearInterval(gpsIntervalId);
            if (syncIntervalId) clearInterval(syncIntervalId);


            console.log("⏹️ Stopped GPS tracking for session:", currentTrackingSession);

            currentTrackingSession = null;
            trackingStartTime = null;
            lastKnownPosition = null; // Clear position tracking

            await openDB();
            await syncWithServer();

            // On stopGPSTracking
            localStorage.removeItem("gps_session_active");

            return true;

        } catch (error) {
            console.error("❌ Failed to stop GPS tracking:", error);
            return false;
        }
    },

    isTrackingActive: function () {
        return gpsIntervalId !== null;
    },

    getCurrentSession: function () {
        return currentTrackingSession;
    },

    getLastPosition: function () {
        return lastKnownPosition;
    },

    syncNow: async function () {
        try {
            await openDB();
            await syncWithServer();
            console.log("🔄 Manual sync completed");
            return true;
        } catch (error) {
            console.error("❌ Manual sync failed:", error);
            return false;
        }
    },
/////////////////////////////////////////////////////////////////////////////////////////////

    // Check if GPS tracking is enabled for current user
    isGpsTrackingEnabled: async function() {
        try {
            const empData = await getCurrentEmployeeData();
            return empData.status === "ok";
        } catch (error) {
            console.error("Failed to check GPS tracking status:", error);
            return false;
        }
    },
///////////////////////////////////////////////////////////////////////////////////////////////

    // Configuration methods
    setMinDistance: function(meters) {
        LOCATION_CONFIG.MIN_DISTANCE_METERS = meters;
        console.log(`📏 Min distance set to ${meters}m`);
    },

    setMinTime: function(seconds) {
        LOCATION_CONFIG.MIN_TIME_SECONDS = seconds;
        console.log(`⏱️ Min time set to ${seconds}s`);
    },

    setMaxAccuracy: function(meters) {
        LOCATION_CONFIG.MAX_ACCURACY_METERS = meters;
        console.log(`🎯 Max accuracy set to ${meters}m`);
    },

    getConfig: function() {
        return { ...LOCATION_CONFIG };
    }
};


//// On page load
//window.addEventListener("load", async () => {
//    if (localStorage.getItem("gps_session_active") === "true") {
//        console.log("♻️ Resuming GPS tracking after reload");
//        await window.odoo.gpsTracker.startGPSTracking();
//    }
//});
//
//// Background sync triggers
//window.addEventListener("visibilitychange", async () => {
//    if (document.visibilityState === "visible") {
//        console.log("👁️ Page visible - sync triggered");
//        await openDB();
//        await syncWithServer();
//    }
//});
//
//window.addEventListener("beforeunload", () => {
//    if (window.odoo.gpsTracker.isTrackingActive()) {
//        console.log("🚪 Page unload - final sync");
//
//        const payload = JSON.stringify({ jsonrpc: "2.0", method: "call", params: { flush: true }});
//        navigator.sendBeacon("/live/gps/update", payload);
//    }
//});



// Debug helper
window.odoo.gpsTracker.getStatus = function () {
    return {
        isActive: this.isTrackingActive(),
        currentSession: this.getCurrentSession(),
        trackingStartTime: trackingStartTime,
        lastPosition: lastKnownPosition,
        config: LOCATION_CONFIG
    };
};

console.log("🎯 Enhanced GPS Tracker with location filtering initialized");
