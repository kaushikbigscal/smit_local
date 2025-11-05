from odoo import models, fields, api
from datetime import datetime


class PaidLeaveCredit(models.Model):
    _inherit = 'hr.employee'

    def _credit_paid_leave(self):
        today = datetime.today().date()

        for employee in self:
            if not employee.join_date:
                continue

            # Fetch all active paid leave configurations
            leave_configs = self.env['paid.leave.config'].search([('active', '=', True)])
            if not leave_configs:
                continue  # No active configuration found, skip processing

            # Calculate years of service
            start_date = employee.join_date if leave_configs[
                                                   0].start_calculation_date == 'join_date' else employee.contract_id.date_start
            years_of_service = (today - start_date).days / 365

            # Loop through all active configurations
            for leave_config in leave_configs:
                # Find the applicable leave credit level for each configuration
                leave_to_credit = 0
                for line in leave_config.leave_credit_lines:
                    if line.min_years <= years_of_service < line.max_years:
                        leave_to_credit = line.leave_credit
                        break  # Once a matching level is found, break the loop

                # If no level is found, skip to the next configuration
                if leave_to_credit == 0:
                    continue

                # Create the leave allocation for the employee
                allocation = self.env['hr.leave.allocation'].create(
                    {
                        'name': leave_config.leave_type_id.name,
                        'holiday_status_id': leave_config.leave_type_id.id,
                        'number_of_days': leave_to_credit,
                        'employee_id': employee.id,
                        'state': 'confirm',
                        'date_from': today,
                    })
                if allocation:
                    allocation.action_validate()

    @api.model
    def _auto_credit_paid_leave(self):
        employees = self.search([('contract_id.date_start', '!=', False)])
        employees._credit_paid_leave()
