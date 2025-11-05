/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";

export class CalendarRuleButtons extends Component {
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
//        this.notification = useService("notification");
        this.state = { loading: true, rules: [] };

        onWillStart(async () => {
            try {
                const rules = await this.orm.call(
                    "calendar.rule",
                    "get_available_rules",
                    []
                );
                this.state.rules = rules || [];
            } finally {
                this.state.loading = false;
            }
        });
    }

    async onClick(rule) {
        try {
            console.log(rule.id)
            const action = await this.orm.call(
                "calendar.rule",
                "action_open_target_model_form",
                [[rule.id]]
            );
            console.log(action)
            if (action) {
                await this.action.doAction(action, {
                    additionalContext: this.props.context || {},
                });
            }
        } catch (e) {
            console.log(e)
        }
    }
}

CalendarRuleButtons.template = "calendar.CalendarRuleButtons";

registry.category("view_widgets").add("calendar_rule_buttons", {
    component: CalendarRuleButtons,
});