/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { CalendarFormView } from "./calendar_form_view";
import { CalendarFormController } from "./calendar_form_controller";
import { serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";

const QUICK_CREATE_CALENDAR_EVENT_FIELDS = {
    name: { type: "string" },
    start: { type: "datetime" },
    start_date: { type: "date" },
    stop_date: { type: "date" },
    stop: { type: "datetime" },
    allday: { type: "boolean" },
    partner_ids: { type: "many2many" },
    videocall_location: { type: "string" },
    description: { type: "string" }
};

function getDefaultValuesFromRecord(data) {
    const context = {};
    for (let fieldName in QUICK_CREATE_CALENDAR_EVENT_FIELDS) {
        if (fieldName in data) {
            let value = data[fieldName];
            const { type } = QUICK_CREATE_CALENDAR_EVENT_FIELDS[fieldName]
            if (type === 'many2many') {
                value = value.records.map((record) => record.resId);
            } else if (type === 'date') {
                value = value && serializeDate(value);
            } else if (type === "datetime") {
                value = value && serializeDateTime(value);
            }
            context[`default_${fieldName}`] = value || false;
        }
    }
    return context;
}

export class CalendarQuickCreateFormController extends CalendarFormController {
    static props = {
        ...CalendarFormController.props,
        goToFullEvent: Function,
        createInTargetModel: Function,
    };

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.isActivityCreation = this.env.context && this.env.context.default_activity_ids;

    }

    get isMeetingMode() {
        const data = this.model.root.data;
        return data && data.event_type === 'meeting';
    }

    get isRecordMode() {
        const data = this.model.root.data;
        return data && data.event_type === 'record';
    }

    async createInTargetModel() {
        const data = this.model.root.data;
        console.log("Data", data);

        if (!this.isRecordMode) {
            return;
        }

        const model = data.x_target_model;
        const { name, description } = data;

        if (!model || !name) {
            this.notification.add(
                "Please select a model and provide a name",
                { type: "danger" }
            );
            return;
        }

        // Build your payload:
        const vals = {
            name: name
        };

        if (description) {
            vals.description = description;
        }

        if (model === 'project.task' && data.is_this_fsm) {
            const [project] = await this.orm.searchRead(
                'project.project',
                [['is_fsm', '=', true]],
                ['id'],
                { limit: 1 }
            );
            if (project) {
                vals.project_id = project.id;
            }
            vals.is_fsm = true;
        }

        try {
            // Create the new record
            const newId = await this.orm.call(model, 'create', [vals]);
            let views = [[false, 'form']];
            let context = {};

            // Special handling for project.task to use project todo view
            if (model === 'project.task') {
                context = {
                    'search_default_open_tasks': 1,
                    'tree_view_ref': 'project_todo.project_task_view_todo_tree'
                };

                // Try to get the project todo view
                try {
                    const todoView = await this.orm.call('ir.ui.view', 'search_read',
                        [['key', '=', 'project_todo.project_task_view_todo_form']],
                        ['id'], { limit: 1 });
                    if (todoView && todoView.length > 0) {
                        views = [[todoView[0].id, 'form']];
                    }
                } catch (error) {
                    // Fallback to default form view if project todo view not found
                    console.log('Project todo view not found, using default form view');
                }
            }
            // Open its form
            this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: model,
                res_id: newId,
                views: views,
                target: 'new',
                context: context
            });

            // Close the quick create dialog
            this.props.close();
        } catch (error) {
            console.error('Error creating record:', error);
            this.notification.add(
                `Error creating record: ${error.message}`,
                { type: "danger" }
            );
        }
    }

    goToFullEvent() {
        const context = getDefaultValuesFromRecord(this.model.root.data)
        this.props.goToFullEvent(context);
    }
}

registry.category("views").add("calendar_quick_create_form_view", {
    ...CalendarFormView,
    Controller: CalendarQuickCreateFormController,
});

export class CalendarQuickCreate extends FormViewDialog {
    static props = {
        ...FormViewDialog.props,
        goToFullEvent: Function,
        createInTargetModel: { type: Function, optional: true },
    };

    setup() {
        super.setup();

        // Simple check - if default_activity_ids exists in any context, it's activity creation
        const context = this.props.context || this.viewProps?.context;
        const isActivityCreation = context && context.default_activity_ids;

        console.log("isActivityCreation:", isActivityCreation);

        const buttonTemplate = isActivityCreation ?
            "calendar.CalendarActivityCreateButtons" :
            "calendar.CalendarRuleCreateButtons";

        Object.assign(this.viewProps, {
            ...this.viewProps,
            buttonTemplate: buttonTemplate,
            goToFullEvent: (contextData) => {
                this.props.goToFullEvent(contextData);
            },
            createInTargetModel: () => this.props.createInTargetModel(),
        });
    }
}