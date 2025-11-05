/** @odoo-module **/

import { Component, onWillStart, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CalendarRulesSidebar extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            rules: [],
            selectedRules: new Set(),
            loading: true,
            error: null
        });

        onWillStart(async () => {
            try {
                await this.loadRules();
            } catch (error) {
                console.error("Failed to load calendar rules:", error);
                this.state.error = null; // Don't show error to user
                this.state.rules = [];
            } finally {
                this.state.loading = false;
            }
        });

        onMounted(() => {
            console.log("✅ CalendarRulesSidebar mounted with", this.state.rules.length, "rules");
        });
    }

    async loadRules() {
        try {
            const result = await this.orm.searchRead("calendar.rule", [], ["id", "name"]);
            this.state.rules = result.filter(rule => rule.active !== false);
        } catch (error) {
            console.warn("calendar.rule model not available:", error.message);
            this.state.rules = [];
            // Don't throw error - just use empty rules
        }
    }

    toggleRule(ruleId) {
        if (this.state.selectedRules.has(ruleId)) {
            this.state.selectedRules.delete(ruleId);
        } else {
            this.state.selectedRules.add(ruleId);
        }

        this.onRulesChanged();
    }

    onRulesChanged() {
        const selectedRuleIds = Array.from(this.state.selectedRules);
        console.log("Selected rules:", selectedRuleIds);

        if (this.env.bus) {
            this.env.bus.trigger('calendar-rules-changed', {
                selectedRules: selectedRuleIds
            });
        }
    }
}

CalendarRulesSidebar.template = "CalendarRulesSidebar";