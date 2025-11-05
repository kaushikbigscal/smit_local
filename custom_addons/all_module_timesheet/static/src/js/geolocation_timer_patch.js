/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

// Helper for RN bridge
function sendLocationCommand(command, sync = false) {
    if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
            type: command,
            sync: !!sync,
        }));
    } else {
        console.log("⚠️ Not inside React Native WebView, skipping...");
    }
}

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        const { name } = clickParams;

//        const GEO_ACTIONS = [
//            //task action
//            "action_start_task_timer",
//            "action_stop_task_timer",
//            //lead action
//            "action_start_lead_timer",
//            "action_stop_lead_timer",
//            //service call action
//            "action_start_service_call_timer",
//            "action_open_end_service_wizard"
//        ];

        // Define mapping of Odoo actions → RN commands
        const GEO_ACTIONS = {
            // task actions
            "action_start_task_timer": { cmd: "STOP_LOCATION_SERVICE", sync: true },
            "action_stop_task_timer": { cmd: "START_LOCATION_SERVICE", sync: false },
            // lead actions
            "action_start_lead_timer": { cmd: "STOP_LOCATION_SERVICE", sync: true },
            "action_stop_lead_timer": { cmd: "START_LOCATION_SERVICE", sync: false },
            // service call actions
            "action_start_service_call_timer": { cmd: "STOP_LOCATION_SERVICE", sync: true },
            "action_open_end_service_wizard": { cmd: "START_LOCATION_SERVICE", sync: false },
        };

        console.log("▶️ Button clicked:", name);

        // Get notification service
        const notification = this.notification || (this.env.services && this.env.services.notification);

        //if (GEO_ACTIONS.includes(name)) {

        if (GEO_ACTIONS[name]) {
            if (!navigator.geolocation) {
                console.error("❌ Geolocation not supported");
                return super.beforeExecuteActionButton(clickParams);
            }

            try {
                const position = await this._getLocation();
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;
                console.log("✅ Location:", latitude, longitude);

                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: latitude,
                    default_longitude: longitude
                };

                // Fire RN command based on action
                const { cmd, sync } = GEO_ACTIONS[name];
                sendLocationCommand(cmd, sync);

            } catch (error) {
                console.error("⚠️ Failed to get geolocation:", error);
                if (notification) {
                    notification.add("Failed to get your location. Please allow location access in your browser.", { type: "warning" });
                }
            }
        }

        return super.beforeExecuteActionButton(clickParams);
    },

    _getLocation() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            });
        });
    }
});
