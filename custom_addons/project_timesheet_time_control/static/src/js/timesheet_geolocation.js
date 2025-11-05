///** @odoo-module **/
//
//import { FormController } from "@web/views/form/form_controller";
//import { patch } from "@web/core/utils/patch";
//
//patch(FormController.prototype, {
//    setup() {
//        super.setup();
//    },
//
//    async beforeExecuteActionButton(clickParams) {
//        const { name } = clickParams;
//        console.log("Action button:", name);
//
//        // Only get location for start_work
//        if (name === 'button_start_work') {
//            console.log("Trying to get location...");
//
//            if (!navigator.geolocation) {
//                console.error("Geolocation is not supported");
//                return super.beforeExecuteActionButton(clickParams);
//            }
//
//            try {
//                const position = await this._getLocation();
//                console.log("Position received:", position);
//
//                // Store location in localStorage for end timer
//                const locationData = {
//                    latitude: position.coords.latitude,
//                    longitude: position.coords.longitude
//                };
//                localStorage.setItem('timesheet_location', JSON.stringify(locationData));
//
//                clickParams.context = {
//                    ...clickParams.context,
//                    default_latitude: position.coords.latitude,
//                    default_longitude: position.coords.longitude
//                };
//            } catch (error) {
//                console.error("Geolocation error:", error);
//            }
//        }
//        // For end_work, use the stored location
//        else if (name === 'button_end_work') {
//            const storedLocation = localStorage.getItem('timesheet_location');
//            if (storedLocation) {
//                const locationData = JSON.parse(storedLocation);
//                clickParams.context = {
//                    ...clickParams.context,
//                    default_latitude: locationData.latitude,
//                    default_longitude: locationData.longitude
//                };
//            }
//        }
//
//        return super.beforeExecuteActionButton(clickParams);
//    },
//
//    _getLocation() {
//        return new Promise((resolve, reject) => {
//            navigator.geolocation.getCurrentPosition(
//                resolve,
//                reject,
//                {
//                    enableHighAccuracy: true,
//                    timeout: 5000,
//                    maximumAge: 0
//                }
//            );
//        });
//    }
//});



/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";

// Patch FormController
patch(FormController.prototype, {
    setup() {
        super.setup();
    },

    async beforeExecuteActionButton(clickParams) {
        const { name } = clickParams;
        console.log("Action button:", name);

        // Only get location for start_work
        if (name === 'button_start_work') {
            console.log("Trying to get location...");

            if (!navigator.geolocation) {
                console.error("Geolocation is not supported");
                return super.beforeExecuteActionButton(clickParams);
            }

            try {
                const position = await this._getLocation();
                console.log("Position received:", position);

                // Store location in localStorage for end timer
                const locationData = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                localStorage.setItem('timesheet_location', JSON.stringify(locationData));

                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: position.coords.latitude,
                    default_longitude: position.coords.longitude
                };
            } catch (error) {
                console.error("Geolocation error:", error);
            }
        }
        // For end_work, use the stored location
        else if (name === 'button_end_work') {
            const storedLocation = localStorage.getItem('timesheet_location');
            if (storedLocation) {
                const locationData = JSON.parse(storedLocation);
                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: locationData.latitude,
                    default_longitude: locationData.longitude
                };
            }
        }

        return super.beforeExecuteActionButton(clickParams);
    },

    _getLocation() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                resolve,
                reject,
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        });
    }
});

// Patch ListController for Tree View
patch(ListController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        const { name } = clickParams;
        console.log("Action button:", name);

        // Only get location for start_work
        if (name === 'button_start_work') {
            console.log("Trying to get location...");

            if (!navigator.geolocation) {
                console.error("Geolocation is not supported");
                return super.beforeExecuteActionButton(clickParams);
            }

            try {
                const position = await this._getLocation();
                console.log("Position received:", position);

                // Store location in localStorage for end timer
                const locationData = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                localStorage.setItem('timesheet_location', JSON.stringify(locationData));

                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: position.coords.latitude,
                    default_longitude: position.coords.longitude
                };
            } catch (error) {
                console.error("Geolocation error:", error);
            }
        }
        // For end_work, use the stored location
        else if (name === 'button_end_work') {
            const storedLocation = localStorage.getItem('timesheet_location');
            if (storedLocation) {
                const locationData = JSON.parse(storedLocation);
                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: locationData.latitude,
                    default_longitude: locationData.longitude
                };
            }
        }

        return super.beforeExecuteActionButton(clickParams);
    },

    _getLocation() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                resolve,
                reject,
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        });
    }
});

// Patch KanbanController for Kanban View
patch(KanbanController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        const { name } = clickParams;
        console.log("Action button:", name);

        // Only get location for start_work
        if (name === 'button_start_work') {
            console.log("Trying to get location...");

            if (!navigator.geolocation) {
                console.error("Geolocation is not supported");
                return super.beforeExecuteActionButton(clickParams);
            }

            try {
                const position = await this._getLocation();
                console.log("Position received:", position);

                // Store location in localStorage for end timer
                const locationData = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                localStorage.setItem('timesheet_location', JSON.stringify(locationData));

                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: position.coords.latitude,
                    default_longitude: position.coords.longitude
                };
            } catch (error) {
                console.error("Geolocation error:", error);
            }
        }
        // For end_work, use the stored location
        else if (name === 'button_end_work') {
            const storedLocation = localStorage.getItem('timesheet_location');
            if (storedLocation) {
                const locationData = JSON.parse(storedLocation);
                clickParams.context = {
                    ...clickParams.context,
                    default_latitude: locationData.latitude,
                    default_longitude: locationData.longitude
                };
            }
        }

        return super.beforeExecuteActionButton(clickParams);
    },

    _getLocation() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                resolve,
                reject,
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        });
    }
});
