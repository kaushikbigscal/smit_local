/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { CalendarQuickCreate } from "@calendar/views/calendar_form/calendar_quick_create";
import { CalendarDashboard } from "@calendar/components/calendar_dashboard/calendar_dashboard";

export class AttendeeCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.user = useService("user");
        this.orm = useService("orm");

        // Add custom state properties to existing parent state
        this.state.isSystemUser = false;
        this.state.isFieldVisitAvailable = false;
        this.state.moduleInfo = {};
        this.state.menuAccess = {};

        onWillStart(async () => {
            this.state.isSystemUser = await this.user.hasGroup('base.group_system');

            // Check if field.visit model is available by trying to access it directly
            try {
                const dashboard = await this.orm.call("calendar.event", "retrieve_dashboard", []);
                this.state.moduleInfo = dashboard.module_info || {};
                this.state.menuAccess = dashboard.menu_access || {};
            } catch (e) {
                console.warn("Failed to load dashboard:", e);
                this.state.moduleInfo = {};
                this.state.menuAccess = {};
            }

            try {
                await this.orm.searchRead("field.visit", [], ["id"], { limit: 1 });
                this.state.isFieldVisitAvailable = true;
            } catch {
                this.state.isFieldVisitAvailable = false;
            }
        });
    }

//    onClickAddButton() {
//        if (!this.state.isFieldVisitAvailable) {
//            console.log('Field visit model not available');
//            return;
//        }
//
//        this.actionService.doAction({
//            type: 'ir.actions.act_window',
//            res_model: 'field.visit',
//            views: [[false, 'form']],
//        }, {
//            additionalContext: this.props.context,
//        });
//    }

    onClickNewMeeting() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'calendar.event',
            views: [[false, 'form']],
            name: 'New Meeting',
        }, {
            additionalContext: this.props.context,
        });
    }

    onClickNewFieldVisit() {
        if (!this.state.isFieldVisitAvailable) {
            console.log('Field visit model not available');
            return;
        }

        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'field.visit',
            views: [[false, 'form']],
            name: 'New Field Visit',
        }, {
            additionalContext: {
                default_field_visit_plan_type: 'customer_wise',
                default_is_unplanned: true,
            },
        });
    }

    onClickNearestCustomer() {
        this.actionService.doAction("calendar_extended.action_res_partner_map", {
            additionalContext: this.props.context,
        });
    }


    goToFullEvent (resId, additionalContext) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'calendar.event',
            views: [[false, 'form']],
            res_id: resId || false,
        }, {
            additionalContext
        });
    }

    getQuickCreateFormViewProps(record) {
        const props = super.getQuickCreateFormViewProps(record);
        const onDialogClosed = () => {
            this.model.load();
        };
        return {
            ...props,
            size: "md",
            goToFullEvent: (contextData) => {
                const fullContext = {
                    ...props.context,
                    ...contextData
                };
                this.goToFullEvent(false, fullContext)
            },
            onRecordSaved: () => onDialogClosed(),
        };
    }

    async editRecord(record, context = {}) {
        if (record.id) {
            return this.goToFullEvent(record.id, context);
        }
    }

    /**
     * @override
     *
     * If the event is deleted by the organizer, the event is deleted, otherwise it is declined.
     */
    deleteRecord(record) {
        if (this.user.partnerId === record.attendeeId && this.user.partnerId === record.rawRecord.partner_id[0]) {
            if (record.rawRecord.recurrency) {
                this.openRecurringDeletionWizard(record);
            } else {
                super.deleteRecord(...arguments);
            }
        } else {
            // Decline event
            this.orm.call(
                "calendar.attendee",
                "do_decline",
                [record.calendarAttendeeId],
            ).then(this.model.load.bind(this.model));
        }
    }

    openRecurringDeletionWizard(record) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'calendar.popover.delete.wizard',
            views: [[false, 'form']],
            view_mode: "form",
            name: 'Delete Recurring Event',
            context: {'default_record': record.id},
            target: 'new'
        }, {
            onClose: () => {
                location.reload();
            },
        });
    }

    configureCalendarProviderSync(providerName) {
        this.actionService.doAction({
            name: _t('Connect your Calendar'),
            type: 'ir.actions.act_window',
            res_model: 'calendar.provider.config',
            views: [[false, "form"]],
            view_mode: "form",
            target: 'new',
            context: {
                'default_external_calendar_provider': providerName,
                'dialog_size': 'medium',
            }
        });
    }


}
AttendeeCalendarController.template = "calendar.AttendeeCalendarController";
AttendeeCalendarController.components = {
    ...AttendeeCalendarController.components,
    CalendarDashboard,
    QuickCreateFormView: CalendarQuickCreate,
}
