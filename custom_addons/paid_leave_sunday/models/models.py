from email.policy import default

from odoo import models, fields, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    worked_sundays_count = fields.Float(string="Sundays Worked", default=0)
    compensation_preferencee = fields.Selection(related='company_id.compensation_preference',
                                                string='Compensation Preference', readonly=True)
    Enable_Sunday_Rule=fields.Boolean(related='company_id.Enable_Sunday_Rule',
                                                string='Enable compensation preference Rule', readonly=True)
    Allow_work_on_sunday=fields.Boolean(
        string='Work on Non-working Day',
        default=False)

class ResCompany(models.Model):
    _inherit = 'res.company'

    Enable_Sunday_Rule = fields.Boolean(
        string='Enable compensation preference Rule',
        help="Check this box to enable the compensation preference selection.",default=False
    )
    compensation_preference = fields.Selection(
        [('extra_pay', 'Extra Pay'), ('paid_time_off', 'Paid Time Off')],
        string='Compensation Preference',
        default='extra_pay',
        help="Choose whether the employee receives extra pay or a compensatory day off for working on Sundays."
    )


    @api.model
    def create_salary_rule(self):
        # Check if the salary rule already exists
        existing_rule = self.env['hr.salary.rule'].search([('code', '=', 'SUNDAY_PAY_RULE')], limit=1)
        if not existing_rule:
            # Create the salary rule if it doesn't exist
            self.env['hr.salary.rule'].create({
                'name': 'Sunday Extra Pay',
                'code': 'SUNDAY_PAY_RULE',
                'category_id': self.env.ref('om_hr_payroll.BASIC').id,  # Adjust the category as needed
                'appear_on_contract': False,
                'is_deduction': False,
                'appears_on_payslip': True,
                'condition_select': 'none',
                'amount_select': 'code',
                'amount_python_compute': """
                        if employee.contract_id and employee.contract_id.wage:
                            if payslip.date_from and payslip.date_to:
                                days_in_month = (payslip.date_to - payslip.date_from).days + 1
                            else:
                                days_in_month = 30
                            daily_salary = employee.contract_id.wage / days_in_month
                            worked_sundays = employee.worked_sundays_count or 0
                            extra_pay = daily_salary * worked_sundays
                            result = extra_pay
                        else:
                            result = 0
                    """,
            })

    @api.onchange('compensation_preference')
    def _onchange_compensation_preference(self):

        # Retrieve the salary rule
        sunday_pay_rule = self.env['hr.salary.rule'].with_context(active_test=False).search([
            ('code', '=', 'SUNDAY_PAY_RULE')
        ], limit=1)

        if self.compensation_preference == 'extra_pay':
            # Create the salary rule if it doesn't exist
            if not sunday_pay_rule:
                self.create_salary_rule()  # Create the salary rule

            if sunday_pay_rule:
                sunday_pay_rule.appears_on_payslip = True
                sunday_pay_rule.active = True  # Activate the rule

        elif self.compensation_preference == 'paid_time_off':
            if sunday_pay_rule:
                sunday_pay_rule.appears_on_payslip = False
                sunday_pay_rule.active = False  # Deactivate the rule


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        res = super(HrPayslip, self).action_payslip_done()
        for payslip in self:
            if payslip.employee_id:
                payslip.employee_id.sudo().write({'worked_sundays_count': 0})

        return res
