# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

from odoo import fields, models, api, _


class PayslipWizards(models.TransientModel):
    _name = 'check.attendance.shortfall'
    _description = "Check Attedance Shortfall"

    employee_ids = fields.Many2many('employee.full.final', 'resign_date', string='Employee Ids')
    full_final_ids = fields.Many2many('employee.full.final', 'last_date', string='Employee Ids')
    leave_ids = fields.Many2many('hr.leave', string='Not Approved Leaves')
    contract_ids = fields.Many2many('hr.contract', string="Contracts Renewal")
    attendance_shortfall_ids = fields.Many2many('hr.attendance.shortfall', string="Attendance Shortfall")
    is_hold_salary = fields.Boolean(string='Is Hold Salary')
    payslip_run_id = fields.Many2one('hr.payslip.run')

    approve_all_leave = fields.Boolean(string='All Leave Approve?')
    remove_all_salary_hold_emp = fields.Boolean(string='Remove all salary hold employee ?')

    field1 = fields.Char("Field1")
    state = fields.Selection(
        [('1', 'Leave Approval'), ('2', 'Attendance Shortfall'), ('3', 'Contact Renewal'), ('4', 'Salary Hold'),
         ('5', 'Full & Final')], default=False)

    select_all = fields.Boolean("Select All")
    lock_previous_payroll = fields.Boolean("Lock Previous Payroll")
    employee_addition = fields.Boolean("Employee Additions")
    employee_separtion = fields.Boolean("Employee Separations")
    employee_confirmation = fields.Boolean("Employee Confirmations")
    employee_data_update = fields.Boolean("Employee Data Updates")
    update_payment_details = fields.Boolean("Update Payment Details")
    salary_revisions = fields.Boolean("Salary Revisions")
    update_one_time_payment = fields.Boolean("Update One Time Payment")
    update_one_time_deductions = fields.Boolean("Update One Time Deductions")
    update_any_other_salary_changes = fields.Boolean("Update Any Other Salary Changes")
    loans_update = fields.Boolean("Loans Update")
    stop_payment = fields.Boolean("Stop Payment")
    update_lop_lwp = fields.Boolean("Update LOP/LWP")
    update_arrears = fields.Boolean("Update Arrears")
    full_final_settlements = fields.Boolean("Full & Final Settlements")
    reimbursement_claims = fields.Boolean("Reimbursement Claims")
    lock_it_declaration = fields.Boolean("Lock IT Declaration")
    download_it_declaration = fields.Boolean("Download IT Declaration")

    @api.onchange('remove_all_salary_hold_emp')
    def remove_all_salary_hold_emp_checkbox(self):
        if self.remove_all_salary_hold_emp == True:
            self.employee_ids = False

    @api.onchange('select_all')
    def select_all_checkbox(self):
        if self.select_all:
            self.lock_previous_payroll = True
            self.employee_addition = True
            self.employee_separtion = True
            self.employee_confirmation = True
            self.employee_data_update = True
            self.update_payment_details = True
            self.salary_revisions = True
            self.update_one_time_payment = True
            self.update_one_time_deductions = True
            self.update_any_other_salary_changes = True
            self.loans_update = True
            self.stop_payment = True
            self.update_lop_lwp = True
            self.update_arrears = True
            self.full_final_settlements = True
            self.reimbursement_claims = True
            self.lock_it_declaration = True
            self.download_it_declaration = True
        else:
            self.lock_previous_payroll = False
            self.employee_addition = False
            self.employee_separtion = False
            self.employee_confirmation = False
            self.employee_data_update = False
            self.update_payment_details = False
            self.salary_revisions = False
            self.update_one_time_payment = False
            self.update_one_time_deductions = False
            self.update_any_other_salary_changes = False
            self.loans_update = False
            self.stop_payment = False
            self.update_lop_lwp = False
            self.update_arrears = False
            self.full_final_settlements = False
            self.reimbursement_claims = False
            self.lock_it_declaration = False
            self.download_it_declaration = False

    def check_condition_step(self):
        check_list = ['lock_previous_payroll', 'employee_addition',
                      'employee_separtion', 'employee_confirmation',
                      'employee_data_update', 'update_payment_details',
                      'salary_revisions', 'update_one_time_payment',
                      'update_one_time_deductions', 'update_any_other_salary_changes',
                      'loans_update', 'stop_payment', 'update_lop_lwp', 'update_arrears',
                      'full_final_settlements', 'reimbursement_claims',
                      'lock_it_declaration', 'download_it_declaration']
        check_dict = self.env['check.attendance.shortfall'].search_read([('id', '=', self.id)])
        count = 0
        bool_list = []
        for i in check_dict[0]:
            if i in check_list:
                count = count + 1
                if check_dict[0][i]:
                    bool_list.append(True)
                else:
                    bool_list.append(False)
        if False in bool_list:
            raise ValidationError("Please Tick Check Box")
        else:
            self.state = '1'

    def check_attendance(self):
        employee_ids = self.env['hr.employee'].search([('company_id', '=', self.payslip_run_id.company_id.id)])
        contract_ids = self.env['hr.contract'].search([('employee_id', 'in', employee_ids.ids), ('state', '=', 'open')])
        day_from = datetime.combine(self.payslip_run_id.date_start, datetime.min.time())
        day_to = datetime.combine(self.payslip_run_id.date_end, datetime.max.time())
        shortfall_ids_list = []
        for contract_id in contract_ids:
            work_data = contract_id.employee_id._get_work_days_data(day_from, day_to, compute_leaves=True)
            attend_report_ids = self.env['hr.attendance'].search(
                [('employee_id', '=', contract_id.employee_id.id), ('check_in', '>=', day_from),
                 ('check_out', '<=', day_to)])

            working_hours = round(sum(attend_report_ids.mapped('worked_hours')))

            if work_data['hours'] < working_hours:
                continue
            else:
                temp_shortfall = work_data['hours'] - working_hours
                temp_shortfall_days = temp_shortfall / contract_ids.resource_calendar_id.hours_per_day
                temp_shortfall_duration = temp_shortfall_days - int(temp_shortfall_days)
                if temp_shortfall_duration < 0.5 and temp_shortfall_duration > 0.0:
                    temp_shortfall_days = int(temp_shortfall_days) + 0.5
                elif temp_shortfall_duration > 0.6:
                    temp_shortfall_days = int(temp_shortfall_days) + 1

                if self.attendance_shortfall_ids:
                    self.attendance_shortfall_ids.unlink()
                data = {
                    'employee_id': contract_id.employee_id.id,
                    'working_hours': working_hours,
                    'actual_hours': work_data['hours'],
                    'shortfall': round(temp_shortfall, 2),
                    'shortfall_days': temp_shortfall_days,
                    'date_start': day_from,
                    'date_end': day_to
                }
                shortfall_ids_list.append((0, 0, data))
        self.attendance_shortfall_ids = shortfall_ids_list

    def approve_all_leaves(self):
        for rec in self.leave_ids.filtered(lambda l: l.state == 'confirm'):
            rec.with_context(from_full_final=True).action_approve()
            self._cr.commit()

    def next_step(self):
        if self.state == False:
            self.check_condition_step()
        elif self.state == '1':
            if self.approve_all_leave:
                self.approve_all_leaves()
            self.check_attendance()
            self.write({'state': '2'})
        elif self.state == '2':
            self.write({'state': '3'})
        elif self.state == '3':
            self.write({'state': '4'})
        elif self.state == '4':
            self.write({'state': '5'})
        return {
            'name': _('Validation Wizard'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'check.attendance.shortfall',
            'res_id': self.id,
            'target': 'new',
        }

    def go_to_previous_wizard(self):

        if self.state == '5':
            self.write({'state': '4'})
        elif self.state == '4':
            self.write({'state': '3'})
        elif self.state == '3':
            self.write({'state': '2'})
        elif self.state == '2':
            self.write({'state': '1'})
        elif self.state == '1':
            self.write({'state': False})
        return {
            'name': _('Validation Wizard'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'check.attendance.shortfall',
            'res_id': self.id,
            'target': 'new',
        }

    def auto_genarate_payslip(self):
        employee = self.env['hr.contract'].search(
            [('date_end', '>=', self.payslip_run_id.date_end),
             ('date_start', '<=', self.payslip_run_id.date_start), ('state', '=', 'open')],
            order='struct_id').employee_id

        current_company_employee = employee.filtered(
            lambda emp: emp.company_id.id == self.payslip_run_id.company_id.id)
        if current_company_employee:
            current_date = date.today()
            employee_list = []
            it_declaration_year = str(current_date.strftime('%Y')) + '-' + str(
                (current_date + relativedelta(years=1)).strftime('%y')) if current_date > date(current_date.year, 3,
                                                                                               31) else str(
                (current_date - relativedelta(years=1)).strftime('%Y')) + '-' + str(current_date.strftime('%y'))
            financial_year = self.env['financial.year'].search([('name', '=', it_declaration_year)])
            if financial_year:
                for employee_id in current_company_employee:
                    it_declaration_year_record = self.env['it.declaration.payslip'].search(
                        [('employee_id', '=', employee_id.id), ('financial_year', '=', financial_year.id)], limit=1,
                        order='create_date desc')
                    if it_declaration_year_record and it_declaration_year_record.status == 'unlocked':
                        employee_list.append(employee_id.name)
            else:
                raise ValidationError(
                    f"It declaration are not created for current Year. Please create for all employee.{employee_list}")

            if len(employee_list) > 1:
                raise ValidationError(
                    "IT Declaration for following employees are not locked. Please lock before you generate payslips.\n" + "\n".join(
                        "- " + employee for employee in employee_list))
            elif len(employee_list) == 1:
                raise ValidationError(
                    "IT Declaration for following employee is not locked. Please lock before you generate payslip.\n- " + str(
                        employee_list[0]))

            payslips = self.env['hr.payslip']

            for employee in current_company_employee:
                ff_employee = False
                full_and_final = False
                if employee.id in self.full_final_ids.employee_id.ids:
                    for full_final in self.full_final_ids:
                        date_end = full_final.last_date
                        ff_employee = employee
                        full_and_final = full_final
                else:
                    date_end = self.payslip_run_id.date_end

                slip_data = self.env['hr.payslip'].onchange_employee_id(self.payslip_run_id.date_start,
                                                                        self.payslip_run_id.date_end, employee.id,
                                                                        contract_id=False)
                blocked = False
                if employee in self.employee_ids.employee_id:
                    blocked = True

                hold_salary_slip = self.env['hr.payslip'].search(
                    [('employee_id', '=', employee.id), ('is_blocked', '=', True)])
                for salary_slip in hold_salary_slip:
                    salary_slip.payslip_run_id = self.payslip_run_id.id

                work_days = [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')]


                # for checkbox in self.attendance_shortfall_ids:
                #     if employee == checkbox.employee_id and checkbox.checkbox == True:
                #         shortfall_days = checkbox.shortfall_days
                #         if shortfall_days > 0:
                #             work_dict = {
                #                 'name': 'Attendance Shortfall',
                #                 'sequence': 6,
                #                 'code': 'SHORTFALL',
                #                 'number_of_days': shortfall_days,
                #                 'number_of_hours': shortfall_days * self.env['hr.contract'].browse(
                #                     slip_data['value'].get('contract_id')).resource_calendar_id.hours_per_day,
                #                 'contract_id': slip_data['value'].get('contract_id')
                #             }
                #             work_days.append((0, 0, work_dict))

                res = {
                    'employee_id': employee.id,
                    'name': slip_data['value'].get('name'),
                    'struct_id': slip_data['value'].get('struct_id'),
                    'contract_id': slip_data['value'].get('contract_id'),
                    'payslip_run_id': self.payslip_run_id.id,
                    'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                    'worked_days_line_ids': work_days,
                    'date_from': self.payslip_run_id.date_start,
                    'date_to': date_end,
                    'credit_note': self.payslip_run_id.credit_note,
                    'company_id': employee.company_id.id,
                    'is_blocked': blocked,
                }
                payslips += self.env['hr.payslip'].create(res)

                # make full&final employee left
                if ff_employee:
                    running_contract = self.env['hr.contract'].search(
                        [('employee_id', '=', ff_employee.id), ('state', '=', 'open')])
                    if running_contract:
                        running_contract.state = 'close'
                if full_and_final:
                    full_and_final.action_done()

            payslips.compute_sheet()
