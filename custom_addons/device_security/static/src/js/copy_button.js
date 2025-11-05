/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

// Register a custom client action for copying UUID
function copyUuidAction(env, action) {
    const uuid = action.params.uuid;
    if (uuid) {
        browser.navigator.clipboard.writeText(uuid).then(() => {
            env.services.notification.add("UUID copied to clipboard!", {
                title: "Success",
                type: "success",
            });
        }).catch((error) => {
            env.services.notification.add("Failed to copy UUID to clipboard", {
                title: "Error",
                type: "danger",
            });
        });
    }
    return Promise.resolve();
}

registry.category("actions").add("copy_uuid_to_clipboard", copyUuidAction);