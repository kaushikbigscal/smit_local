/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart } = owl;

console.log("🚀 menu_refresh.js is loading...");

export class MenuRefresher extends Component {
    setup() {
        try {
            this.bus = useService("bus_service");
            console.log("📡 Listening for refresh_template_menu event...");
            this.bus.addEventListener("refresh_template_menu", () => {
                console.log("🔥 Event Received: refresh_template_menu");
                this.refreshMenu();
            });

            // Check config parameter on load
            onWillStart(async () => {
                try {
                    const config = await this.env.services.orm.call(
                        "ir.config_parameter",
                        "get_param",
                        ["refresh_template_menu"]
                    );
                    console.log("🔄 Config Parameter Value: ", config);

                    if (config === "True") {
                        console.log("📢 refresh_template_menu detected, refreshing menu...");
                        this.refreshMenu();
                    }
                } catch (rpcError) {
                    console.error("❌ Error fetching config parameter:", rpcError);
                }
            });
        } catch (setupError) {
            console.error("❌ Error setting up MenuRefresher:", setupError);
        }
    }

    refreshMenu() {
        console.log("🔄 Refreshing menu dynamically...");
        location.reload();  // Refresh only the menu
    }
}

// ✅ Correct way to register a service in Odoo
registry.category("services").add("menu_refresher", {
    start(env) {
        return new MenuRefresher(env);
    },
});

console.log("✅ MenuRefresher service registered correctly!");
