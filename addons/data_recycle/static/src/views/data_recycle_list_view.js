/** @odoo-module **/

import { DataCleaningCommonListController } from "@data_recycle/views/data_cleaning_common_list";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";

export class DataRecycleListController extends DataCleaningCommonListController {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    /**
     * Validate all the records selected
     */
    async onValidateClick() {
        const record_ids = await this.getSelectedResIds();

        await this.orm.call('data_recycle.record', 'action_validate', [record_ids]);
        await this.model.load();
    }
    /**
     * Show only archived records
     */
    async onViewArchivedClick() {
        await this.action.doAction('data_recycle.data_recycle_record_action_view_error_log_archived');
    }
    async onViewDeletedClick() {
        await this.action.doAction('data_recycle.data_recycle_record_action_view_error_log_deleted');
    }
}

registry.category('views').add('data_recycle_list', {
    ...listView,
    Controller: DataRecycleListController,
    buttonTemplate: 'DataRecycle.buttons',
});

