/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProjectTaskCalendarController } from "@project/views/project_task_calendar/project_task_calendar_controller";

export class FsmProjectTaskCalendarController extends ProjectTaskCalendarController {

    setup() {
        super.setup(...arguments);

        // Check if we're in FSM mode
        const isFsmMode = this.env.searchModel.context.fsm_mode || false;

        if (isFsmMode) {
            // Override the display name for FSM mode
            this.env.config.setDisplayName(
                this.env.config.getDisplayName().replace(" - Tasks by Deadline", "") + _t(" - Calls by Deadline")
            );
        }
    }

    get editRecordDefaultDisplayText() {
        // Check if we're in FSM mode
        const isFsmMode = this.env.searchModel.context.fsm_mode || false;

        if (isFsmMode) {
            return _t("New Call");
        }

        // Return the parent's default text for non-FSM mode
        return super.editRecordDefaultDisplayText;
    }
}