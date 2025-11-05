/** @odoo-module **/

//qr_scanner_action.js

import { registry } from "@web/core/registry";
import { QrScannerDialog } from "./qr_scanner_dialog";

const actionRegistry = registry.category("actions");

actionRegistry.add("open_qr_scanner_action", (env, action) => {
    const dialog = env.services.dialog;
    dialog.add(QrScannerDialog, {
        title: "Scan QR Code",
    });
});


///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { QrScannerDialog } from "./qr_scanner_dialog";
//
//const actionRegistry = registry.category("actions");
//
//actionRegistry.add("open_qr_scanner_action", (env, action) => {
//    const dialog = env.services.dialog;
//    dialog.add(QrScannerDialog, {
//        title: "Scan QR Code",
//        size: "large",
//    });
//});
