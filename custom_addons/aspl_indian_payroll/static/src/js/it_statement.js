/** @odoo-module **/

import { registry } from "@web/core/registry";
import { onWillStart, useState } from "@odoo/owl";
import { Component } from  "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class ItStatement extends Component {
    static template = "ItStatement";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            login_employee: []
        })
        onWillStart(async () => {
            this.state.login_employee = {}
            var empDetails = await this.orm.call('hr.employee', 'get_user_employee_details_payslip', [])
            if ( empDetails ){
                this.state.login_employee = empDetails
            }
            console.log(empDetails)
        });
    }
}
registry.category("actions").add("it_statement", ItStatement);