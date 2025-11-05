/** @odoo-module **/

import { Component, useRef, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { session } from "@web/session";


class GpsTrackingMap extends Component {
    setup() {
        this.mapRef = useRef("map");
        this.state = useState({
            date: new Date().toISOString().split("T")[0],
            employeeId: session.is_system ? null : session.user_id.employee_id,
            isAdmin: session.is_system,
            loading: true,
            info: null,
            employees: [],
        });

        onMounted(async () => {
            await this.loadEmployeeData();
            await this.renderMap();
        });
    }

    async loadEmployeeData() {
        const { date, employeeId } = this.state;

        const res = await jsonrpc("/live/gps/employees_data", {
            date_str: date,
            employee_id: parseInt(employeeId),
        });

        if (res.error) {
            console.error("❌ Failed to load employee data", res.error);
////////////////////////////////////////////////////////////////////////////////////////

            if (res.error.includes("GPS tracking is disabled")) {
                this.state.info = {
                    error: res.error,
                    gps_disabled: true
                };
            }
////////////////////////////////////////////////////////////////////////////////////////
            return;
        }
        this.state.employees = res.employees || [];
        this.state.info = res.employee_info || {};

        if (!this.state.employeeId && res.employee_info?.id) {
            this.state.employeeId = res.employee_info.id;
        }
    }

    // Enhanced clustering function to group nearby points properly
    clusterNearbyPoints(data, threshold = 0.0001) { // ~11 meters
        const clusters = [];
        const processed = new Set();

        data.forEach((point, index) => {
            if (processed.has(index)) return;

            const cluster = [index];
            processed.add(index);

            // Find nearby points
            for (let i = index + 1; i < data.length; i++) {
                if (processed.has(i)) continue;

                const distance = this.calculateDistance(
                    data[index].lat, data[index].lng,
                    data[i].lat, data[i].lng
                );

                if (distance <= threshold) {
                    cluster.push(i);
                    processed.add(i);
                }
            }

            clusters.push(cluster);
        });
        return clusters;
    }

    // Calculate distance between two points (Haversine formula)
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lng2 - lng1) * Math.PI / 180;

        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

        return R * c;
    }

    // Check if travel between two points is physically impossible
    isSuspiciousTravel(point1, point2) {
        if (!point1.timestamp || !point2.timestamp) return false;

        const distance = this.calculateDistance(point1.lat, point1.lng, point2.lat, point2.lng);
        const time1 = new Date(point1.timestamp);
        const time2 = new Date(point2.timestamp);
        const timeDiffSeconds = Math.abs(time2 - time1) / 1000;
        const timeDiffHours = timeDiffSeconds / 3600;

        // If no time difference, not suspicious
        if (timeDiffSeconds < 10) return false;

        // Calculate required speed in km/h
        const requiredSpeedKmh = (distance / 1000) / timeDiffHours;

        // Suspicious if speed > 120 km/h (considering two-wheeler mode)
        // Also suspicious if significant distance (>50km) covered in very short time (<300 seconds = 5 minutes)
        const isHighSpeed = requiredSpeedKmh > 120;
        const isTeleportation = distance > 50000 && timeDiffSeconds < 300; // 50km in 5 minutes

        if (isHighSpeed || isTeleportation) {
            console.log(`🚨 Suspicious travel detected: ${(distance/1000).toFixed(2)}km in ${timeDiffSeconds}s = ${requiredSpeedKmh.toFixed(2)} km/h`);
            return true;
        }
        return false;
    }

    // Enhanced function to detect suspicious points including start/end points
    detectSuspiciousPoints(data) {
        const suspiciousPoints = new Set();

        // Check each point for suspicious travel from previous point
        for (let i = 1; i < data.length; i++) {
            if (this.isSuspiciousTravel(data[i-1], data[i])) {
                // Mark both points as suspicious for extreme cases
                suspiciousPoints.add(i-1);
                suspiciousPoints.add(i);
            }
        }

        // Mark points as suspicious in the data
        suspiciousPoints.forEach(index => {
            data[index].suspicious = true;
            data[index].suspiciousReason = "Impossible travel speed/distance";
        });

        return data;
    }

    // Apply smart jitter only to clustered points (not suspicious ones)
    applySmartJitter(data) {
        const clusters = this.clusterNearbyPoints(data);
        clusters.forEach(cluster => {
            if (cluster.length > 1) {
                // Only apply jitter if points are not already marked as suspicious
                const hasOriginalSuspicious = cluster.some(idx => data[idx].suspicious === true);

                if (!hasOriginalSuspicious) {
                    // Find cluster center
                    const centerLat = cluster.reduce((sum, idx) => sum + data[idx].lat, 0) / cluster.length;
                    const centerLng = cluster.reduce((sum, idx) => sum + data[idx].lng, 0) / cluster.length;

                    // Apply circular jitter around center
                    cluster.forEach((pointIdx, clusterIdx) => {
                        if (clusterIdx > 0) { // Keep first point as is
                            const angle = (2 * Math.PI * clusterIdx) / cluster.length;
                            const jitter = 0.00003; // ~3 meters

                            // Store original coordinates
                            data[pointIdx].originalLat = data[pointIdx].lat;
                            data[pointIdx].originalLng = data[pointIdx].lng;

                            // Apply jitter
                            data[pointIdx].lat = centerLat + Math.cos(angle) * jitter;
                            data[pointIdx].lng = centerLng + Math.sin(angle) * jitter;

                            // Mark as jittered (not suspicious)
                            data[pointIdx].isJittered = true;
                        }
                    });
                }
            }
        });

        return data;
    }

    async renderMap() {
        const container = this.mapRef.el;
        if (!container) return;

        this.state.loading = true;

        const { date, employeeId, isAdmin } = this.state;
        if (isAdmin && !employeeId) {
            this.state.loading = false;
            return;
        }
//////////////////////////////////////////////////////////////////////////////////////////
        // Check if GPS tracking is disabled
        if (this.state.info?.gps_disabled) {
            this.state.loading = false;
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${this.state.info.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }
////////////////////////////////////////////////////////////////////////////////////////////
        const [apiKey, gpsDataResp] = await Promise.all([
            jsonrpc("/get/google/maps/api/key", {employee_id: employeeId}),
            jsonrpc("/live/gps/path", { date_str: date, employee_id: employeeId }),
        ]);

        this.apiKey = apiKey;   // Save API key on the class instance

        this.state.loading = false;
///////////////////////////////////////////////////////////////////////////////////////////

        // Handle GPS tracking disabled error from API key endpoint (API key fetch request)
        if (apiKey.error && apiKey.error.includes("GPS tracking is disabled")) {
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${apiKey.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Handle GPS path data errors (GPS path data fetch request)
        if (gpsDataResp.error && gpsDataResp.error.includes("GPS tracking is disabled")) {
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>GPS Tracking Disabled</h4>
                        <p>${gpsDataResp.error}</p>
                        <p>Please contact your administrator to enable GPS tracking.</p>
                    </div>
                </div>
            `;
            return;
        }
///////////////////////////////////////////////////////////////////////////////////////////

        // Handle new response format
        const gpsData = gpsDataResp.points || gpsDataResp;
        this.state.info.speed_kmh = gpsDataResp.speed_kmh;
        this.state.info.traveled_duration = gpsDataResp.traveled_duration;
        this.state.info.speed_is_unusual = gpsDataResp.speed_kmh > 100;

        // Handle suspicious points more carefully
        this.state.info.any_suspicious = gpsDataResp.any_suspicious;

        if (gpsDataResp.duration_s) {
            const totalSeconds = Math.floor(gpsDataResp.duration_s);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;
            this.state.info.duration = [
                hours.toString().padStart(2, '0'),
                minutes.toString().padStart(2, '0'),
                seconds.toString().padStart(2, '0')
            ].join(':');
        } else {
            this.state.info.duration_s = null;
        }

        if (!gpsData || gpsData.length < 2) {
            this.state.info.distance = null;
            this.state.info.duration = null;
//////////////////////////////////////////////////////////////////////////////////////////
            container.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 400px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;">
                    <div style="text-align: center; color: #6c757d;">
                        <h4>No GPS Data Found</h4>
                        <p>No GPS tracking data found for the selected date.</p>
                        <p>Make sure GPS tracking was active during attendance.</p>
                    </div>
                </div>
            `;
            return;
//////////////////////////////////////////////////////////////////////////////////////////
        }

        if (!window.google || !window.google.maps) {
            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey.api_key}&libraries=marker&v=weekly`;
            script.async = true;
            script.defer = true;
            script.onload = () => this.initMap(container, gpsData);
            document.head.appendChild(script);
        } else {
            this.initMap(container, gpsData);
        }
    }

    async initMap(container, data) {
        if (!Array.isArray(data) || data.length < 2) return;

        // First, detect suspicious points based on travel patterns
        const dataWithSuspiciousDetection = this.detectSuspiciousPoints([...data]);

        // Then apply smart jitter to handle overlapping points (but preserve suspicious ones)
        const processedData = this.applySmartJitter(dataWithSuspiciousDetection);

        // Update suspicious info based on our detection
        this.state.info.any_suspicious = processedData.some(p => p.suspicious === true);

        const origin = { lat: processedData[0].lat, lng: processedData[0].lng };
        const destination = {
            lat: processedData[processedData.length - 1].lat,
            lng: processedData[processedData.length - 1].lng
        };

        const map = new google.maps.Map(container, {
            zoom: 14,
            center: origin,
            mapId: "DEMO_MAP_ID",
            gestureHandling: "cooperative",
        });

        // Create markers with enhanced categorization
//        processedData.forEach((p, i) => {
//            const marker = new google.maps.marker.AdvancedMarkerElement({
//                map,
//                position: { lat: p.lat, lng: p.lng },
//
//                content: (() => {
//                    const el = document.createElement("div");
//
//                    const circle = document.createElement("div");
//                    const label = document.createElement("span");
//
//                    let isCallPoint = false;
//
//                    // Suspicious / jitter / route handling
//                    if (p.suspicious === true && !p.isJittered) {
//                        if (i === 0) {
//                            circle.style.backgroundColor = "purple";
//                            circle.style.border = "2px solid green";
//                            circle.title = "Suspicious Start Point";
//                        } else if (i === processedData.length - 1) {
//                            circle.style.backgroundColor = "purple";
//                            circle.style.border = "2px solid red";
//                            circle.title = "Suspicious End Point";
//                        } else {
//                            circle.style.backgroundColor = "purple";
//                            circle.style.border = "2px solid red";
//                            circle.title = "Suspicious Point - Impossible Travel";
//                        }
//                    } else if (p.isJittered) {
//                        circle.style.backgroundColor = "orange";
//                        circle.title = "Clustered Point";
//                    }
//                    // Call start / end = red pin only (no bg circle, no number)
//                    else if (p.tracking_type === "call_start") {
//                        isCallPoint = true;
//                        circle.innerHTML = "📍";
//                        circle.style.fontSize = "22px";
//                        circle.title = "Call Start Point";
//                    } else if (p.tracking_type === "call_end") {
//                        isCallPoint = true;
//                        circle.innerHTML = "📍";
//                        circle.style.fontSize = "22px";
//                        circle.title = "Call End Point";
//                    }
//                    // Normal route points
//                    else if (i === 0) {
//                        circle.style.backgroundColor = "green";
//                        circle.title = "Start Point";
//                    } else if (i === processedData.length - 1) {
//                        circle.style.backgroundColor = "red";
//                        circle.title = "End Point";
//                    } else {
//                        circle.style.backgroundColor = "yellow";
//                        circle.title = "Route Point";
//                    }
//
//
//                    // Common styles
//                    circle.style.display = "flex";
//                    circle.style.alignItems = "center";
//                    circle.style.justifyContent = "center";
//                    circle.style.position = "relative";
//
//                    if (!isCallPoint) {
//                        // Circle shape only for non-call points
//                        circle.style.width = "22px";
//                        circle.style.height = "22px";
//                        circle.style.borderRadius = "50%";
//                        circle.style.boxShadow = "0 0 3px #000";
//                        circle.style.fontSize = "11px";
//                        circle.style.color = "black";
//                        circle.style.fontWeight = "bold";
//                    }
//
//                    // Number inside circle
//                    label.textContent = (i + 1).toString();
//                    circle.appendChild(label);
//                    el.appendChild(circle);
//                    return el;
//
//                })(),
//
//            });
//
//            // Enhanced info window with suspicious details
//            const infoWindow = new google.maps.InfoWindow({
//                content: `
//                    <div>
//                        <strong>Position:</strong> ${i + 1}/${processedData.length}<br/>
//                        <strong>Lat:</strong> ${p.originalLat || p.lat}<br/>
//                        <strong>Lng:</strong> ${p.originalLng || p.lng}<br/>
//                        <strong>Time:</strong> ${p.timestamp ? p.timestamp.replace('T', ' ').replace('Z', '') : ''}<br/>
//                        <strong>Type:</strong> ${p.tracking_type}<br/>
//                        ${(p.tracking_type === 'call_start' || p.tracking_type === 'call_end') ? `<strong>Customer:</strong> ${p.customer_name || ''}<br/>` : ''}
//                        ${p.isJittered ? '<span style="color:orange;font-weight:bold;">Clustered Point</span><br/>' : ''}
//                        ${p.suspicious === true ? `<span style="color:red;font-weight:bold;">⚠️ SUSPICIOUS!</span><br/><span style="color:red;font-size:12px;">${p.suspiciousReason || 'Unknown reason'}</span><br/>` : ''}
//                    </div>
//                `
//            });
//
//            marker.addListener("click", () => {
//                infoWindow.open({
//                    anchor: marker,
//                    map,
//                    shouldFocus: false,
//                });
//            });
//
//        });

        processedData.forEach((p, i) => {
            const isVisiblePoint =
                p.tracking_type === "call_start" ||
                p.tracking_type === "call_end" ||
                i === 0 ||
                i === processedData.length - 1 ||
                p.suspicious === true;

            if (!isVisiblePoint) return; // Skip creating markers for normal route points

            const marker = new google.maps.marker.AdvancedMarkerElement({
                map,
                position: { lat: p.lat, lng: p.lng },
                content: (() => {
                    const el = document.createElement("div");
                    const circle = document.createElement("div");
                    const label = document.createElement("span");
                    let isCallPoint = false;

                    // Style points
                    if (p.isJittered) {
                        circle.style.backgroundColor = "orange";
                        circle.title = "Clustered Point";
                    } else if (p.tracking_type === "call_start") {
                        isCallPoint = true;
                        circle.innerHTML = "📍";
                        circle.style.fontSize = "22px";
                        circle.title = "Call Start Point";
                    } else if (p.tracking_type === "call_end") {
                        isCallPoint = true;
                        circle.innerHTML = "📍";
                        circle.style.fontSize = "22px";
                        circle.title = "Call End Point";
                    } else if (i === 0) {
                        circle.style.backgroundColor = "green";
                        circle.title = "Start Point";
                    } else if (i === processedData.length - 1) {
                        circle.style.backgroundColor = "red";
                        circle.title = "End Point";
                    } else if (p.suspicious === true) {
                        circle.style.backgroundColor = "purple";
                        circle.style.border = "2px solid red";
                        circle.title = "Suspicious Point";
                    }

                    // Common styling for non-call points
                    if (!isCallPoint) {
                        circle.style.display = "flex";
                        circle.style.alignItems = "center";
                        circle.style.justifyContent = "center";
                        circle.style.position = "relative";
                        circle.style.width = "22px";
                        circle.style.height = "22px";
                        circle.style.borderRadius = "50%";
                        circle.style.boxShadow = "0 0 3px #000";
                        circle.style.fontSize = "11px";
                        circle.style.color = "black";
                        circle.style.fontWeight = "bold";
                    }

                    label.textContent = (i + 1).toString();
                    circle.appendChild(label);
                    return circle;
                })(),
            });


            const formatTimestamp = (timestamp) => {
                if (!timestamp) return '';

                try {
                    // Force parse as UTC by adding 'Z' if not present
                    let utcTimestamp = timestamp;

                    // If timestamp doesn't have timezone info, treat it as UTC
                    if (!timestamp.endsWith('Z') && !timestamp.includes('+') && !timestamp.includes('T')) {
                        // Format: "2025-09-30 08:49:06" -> "2025-09-30T08:49:06Z"
                        utcTimestamp = timestamp.replace(' ', 'T') + 'Z';
                    } else if (timestamp.includes('T') && !timestamp.endsWith('Z')) {
                        utcTimestamp = timestamp + 'Z';
                    }

                    // Parse as UTC
                    const date = new Date(utcTimestamp);

                    if (isNaN(date.getTime())) {
                        return timestamp;
                    }

                    // Get user's timezone from Odoo session
                    const userTimezone = session.user_context.tz || Intl.DateTimeFormat().resolvedOptions().timeZone;

                    // Convert UTC to user's timezone
                    return new Intl.DateTimeFormat('en-GB', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false,
                        timeZone: userTimezone
                    }).format(date).replace(',', '');

                } catch (error) {
                    console.error('Error formatting timestamp:', timestamp, error);
                    return timestamp;
                }
            };
//                        ${(p.tracking_type === 'call_start' || p.tracking_type === 'call_end') ? `<strong>Customer:</strong> ${p.customer_name || 'N/A' }<br/>` : ''}

            // Info window only for visible points
            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <div>
                        ${(p.tracking_type === 'call_start' || p.tracking_type === 'call_end')
                            ? (
                                p.customer_name
                                    ? `<strong>Customer:</strong>  ${p.customer_name}<br/>`
                                    : p.title
                                        ? `<strong>Title:</strong>  ${p.title}<br/>`
                                        : `<strong>Customer:</strong> N/A<br/>`
                            )
                            : ''
                        }
                        <strong>Position:</strong> ${i + 1}/${processedData.length}<br/>
                        <strong>Lat:</strong> ${p.originalLat || p.lat}<br/>
                        <strong>Lng:</strong> ${p.originalLng || p.lng}<br/>
                        <strong>Time:</strong> ${formatTimestamp(p.timestamp)}<br/>
                        <strong>Type:</strong> ${p.tracking_type}<br/>
                        ${p.isJittered ? '<span style="color:orange;font-weight:bold;">Clustered Point</span><br/>' : ''}
                        ${p.suspicious === true ? `<span style="color:red;font-weight:bold;">⚠️ SUSPICIOUS!</span><br/><span style="color:red;font-size:12px;">${p.suspiciousReason || 'Unknown reason'}</span><br/>` : ''}
                    </div>
                `
            });

            marker.addListener("click", () => {
                infoWindow.open({
                    anchor: marker,
                    map,
                    shouldFocus: false,
                });
            });
        });


        // Create route using original coordinates (not jittered)
        const routeData = data.map(p => ({ lat: p.lat, lng: p.lng }));
        const routeOrigin = routeData[0];
        const routeDestination = routeData[routeData.length - 1];
        const directions = new google.maps.DirectionsService();

        async function buildBatchRoute(routeData, map, minDistanceMeters = 200) {
            const fullPath = [];
            const MAX_WAYPOINTS = 25; // origin + destination + 23 stops
            const directions = new google.maps.DirectionsService();

            let totalDistance = 0;
            let totalDuration = 0;

            // Helper: request a Directions API call
            function fetchRoute(origin, destination, waypoints = []) {
                return new Promise(resolve => {
                    directions.route({
                        origin,
                        destination,
                        waypoints,
                        travelMode: google.maps.TravelMode.TWO_WHEELER, // or DRIVING
                        optimizeWaypoints: true,
                    }, (res, status) => {
                        if (status === "OK") {
                            // accumulate distance + duration
                            res.routes[0].legs.forEach(leg => {
                                totalDistance += leg.distance.value;
                                totalDuration += leg.duration.value;
                            });

                            resolve(res.routes[0].overview_path);
                        } else {
                            console.error("Directions failed:", status, origin, destination);
                            resolve([]);
                        }
                    });
                });
            }

            // Helper: reduce waypoints to remove close points
            function reduceWaypoints(points, minDistanceMeters) {
                if (!points.length) return [];
                const reduced = [points[0]];
                let last = points[0];

                function getDistance(p1, p2) {
                    const R = 6371e3;
                    const φ1 = p1.lat * Math.PI / 180;
                    const φ2 = p2.lat * Math.PI / 180;
                    const Δφ = (p2.lat - p1.lat) * Math.PI / 180;
                    const Δλ = (p2.lng - p1.lng) * Math.PI / 180;
                    const a = Math.sin(Δφ/2)**2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ/2)**2;
                    return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
                }

                for (let i = 1; i < points.length; i++) {
                    if (getDistance(last, points[i]) >= minDistanceMeters) {
                        reduced.push(points[i]);
                        last = points[i];
                    }
                }

                // always add final destination
                if (reduced[reduced.length - 1] !== points[points.length - 1]) {
                    reduced.push(points[points.length - 1]);
                }

                return reduced;
            }

            // Reduce points first
            const reducedPoints = reduceWaypoints(routeData, minDistanceMeters);

            // Process in batches of MAX_WAYPOINTS
            for (let i = 0; i < reducedPoints.length; i += MAX_WAYPOINTS - 1) {
                const chunk = reducedPoints.slice(i, i + MAX_WAYPOINTS);
                if (chunk.length < 2) break;

                const origin = chunk[0];
                const destination = chunk[chunk.length - 1];
                const waypoints = chunk.slice(1, -1).map(p => ({ location: p, stopover: false }));

                const segment = await fetchRoute(origin, destination, waypoints);
                fullPath.push(...segment);
            }

            // Draw final polyline
            new google.maps.Polyline({
                path: fullPath,
                strokeColor: "#53ff1a",
                strokeOpacity: 1.0,
                strokeWeight: 5,
                map: map
            });

            // Return results
            return {
                reducedPoints,
                totalDistance, // meters
                totalDuration  // seconds
            };
        }

        const { reducedPoints, totalDistance, totalDuration } = await buildBatchRoute(routeData, map, 200);

        this.state.info.distance = (totalDistance / 1000).toFixed(2) + " km";
        this.state.info.duration = Math.round(totalDuration / 60) + " mins";



//  original code
//        const directions = new google.maps.DirectionsService();
//        const renderer = new google.maps.DirectionsRenderer({
//            suppressMarkers: true,
//            polylineOptions: {
//                strokeColor: this.state.info.any_suspicious ? "#ff5733" : "#53ff1a", // Red if suspicious
//                strokeWeight: 5,
//            },
//        });
//        renderer.setMap(map);
//
//        directions.route(
//            {
//                origin: routeOrigin,
//                destination: routeDestination,
//                waypoints: routeData.slice(1, -1).map(p => ({
//                    location: { lat: p.lat, lng: p.lng },
//                    stopover: false
//                })),
//                travelMode: google.maps.TravelMode.WALKING,
//            },
//            (res, status) => {
//                if (status === "OK") renderer.setDirections(res);
//            }
//        );

//        const matrixService = new google.maps.DistanceMatrixService();
//        matrixService.getDistanceMatrix({
//            origins: [routeOrigin],
//            destinations: [routeDestination],
//            travelMode: google.maps.TravelMode.TWO_WHEELER  ,
//            unitSystem: google.maps.UnitSystem.METRIC,
//        }, (response, status) => {
//            if (status === "OK") {
//                const result = response.rows[0].elements[0];
//                if (result.status === "OK") {
//                    this.state.info.distance = result.distance.text;
//                    this.state.info.duration = result.duration.text;
//                }
//            } else {
//                console.error("❌ DistanceMatrix failed:", status);
//            }
//        });
    }

    async onChangeFilter(ev) {
        const name = ev.target.name;
        const value = ev.target.value;
        this.state[name] = value;
        await this.loadEmployeeData();
        await this.renderMap();
    }

    static template = "field_service_tracking.tracking_route_template";
}

registry.category("actions").add("gps_tracking_route_map", GpsTrackingMap);