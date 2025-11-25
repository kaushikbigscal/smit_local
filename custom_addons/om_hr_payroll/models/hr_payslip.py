import babel
from datetime import date, datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_payslip_download = fields.Boolean(string="Allow Payslip Download")
    days_allowed = fields.Integer(string="Enter Days Limit")
    months_allowed = fields.Integer(string="Past Months Payslip Download Limit", default=3)

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('hr_payroll.allow_payslip_download',
                                                         self.allow_payslip_download)
        self.env['ir.config_parameter'].sudo().set_param('hr_payroll.days_allowed', self.days_allowed)
        self.env['ir.config_parameter'].sudo().set_param('hr_payroll.months_allowed', self.months_allowed)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()

        res.update(
            allow_payslip_download=self.env['ir.config_parameter'].sudo().get_param('hr_payroll.allow_payslip_download',
                                                                                    default=False),
            days_allowed=self.env['ir.config_parameter'].sudo().get_param('hr_payroll.days_allowed', default=10),
            months_allowed=self.env['ir.config_parameter'].sudo().get_param('hr_payroll.months_allowed', default=3)
        )
        return res


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Pay Slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
                                help='Defines the rules that have to be applied to this payslip, accordingly '
                                     'to the contract chosen. If you let empty the field contract, this field isn\'t '
                                     'mandatory anymore and thus the rules applied will be all the rules set on the '
                                     'structure of all contracts of the employee valid for the chosen period')
    name = fields.Char(string='Payslip Name')
    number = fields.Char(string='Reference', copy=False)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='Date To', required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    # this is chaos: 4 states are defined, 3 are used ('verify' isn't) and 5 exist ('confirm' seems to have existed)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""")
    line_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Payslip Lines')
    company_id = fields.Many2one(
        'res.company', string='Company', copy=False,
        default=lambda self: self.env.company
    )
    worked_days_line_ids = fields.One2many(
        'hr.payslip.worked_days', 'payslip_id',
        string='Payslip Worked Days', copy=True
    )
    input_line_ids = fields.One2many(
        'hr.payslip.input', 'payslip_id',
        string='Payslip Inputs', copy=True
    )
    paid = fields.Boolean(string='Made Payment Order ? ', copy=False)
    note = fields.Text(string='Internal Note')
    contract_id = fields.Many2one('hr.contract', string='Contract')
    details_by_salary_rule_category = fields.One2many('hr.payslip.line',
                                                      compute='_compute_details_by_salary_rule_category',
                                                      string='Details by Salary Rule Category')
    credit_note = fields.Boolean(string='Credit Note',
                                 help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches', copy=False)
    payslip_count = fields.Integer(compute='_compute_payslip_count', string="Payslip Computation Details")

    def action_view_payslip_form(self):
        """Preview the payslip report as a PDF in the browser."""
        self.ensure_one()
        pdf_url = f"/report/pdf/om_hr_payroll.action_report_hr_payslip/{self.id}"

        return {
            'type': 'ir.actions.act_url',
            'url': pdf_url,
            'target': 'new',  # Opens in a new tab
        }

    # ---------------------------------for amount in word --------------------
    net_amount_in_word = fields.Text(string='Net Amount in Words', compute='_compute_net_amount_in_word')

    def _compute_net_amount_in_word(self):
        for record in self:
            payslip_records = self.env['hr.payslip'].search([('line_ids.code', '=', 'NET')], limit=1)
            if payslip_records:
                net_line = payslip_records.line_ids.filtered(lambda line: line.code == 'NET')
                net_salary_total = round(net_line.total)
                record.net_amount_in_word = self.num2words(net_salary_total)
            else:
                record.net_amount_in_word = 'Zero Rupees'

    # ----------------------------------------------------- for word converter
    def num2words(self, num):
        """Convert salary numbers to words including rupees and paisa."""
        units = (
            'Zero', 'One', 'Two', 'Three', 'Four', 'Five',
            'Six', 'Seven', 'Eight', 'Nine', 'Ten',
            'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
            'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen', 'Twenty',
            'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'
        )

        def _convert_group(n):
            if 0 <= n < 20:
                return units[n]
            elif 20 <= n < 100:
                return units[20 + (n // 10) - 2] + ('' if n % 10 == 0 else ' ' + units[n % 10])
            elif 100 <= n < 1000:
                return units[n // 100] + ' Hundred' + ('' if n % 100 == 0 else ' and ' + _convert_group(n % 100))

        if num == 0:
            return 'Zero Rupees'

        # Split number into rupees and paisa
        rupees = int(num)
        paisa = int(round((num - rupees) * 100))

        if rupees >= 10000000:
            return 'Out of Range'

        result = ''

        # Handle Crores
        if rupees >= 100000:
            crores = rupees // 10000000
            if crores > 0:
                result += _convert_group(crores) + ' Crore '
            rupees = rupees % 10000000

        # Handle Lakhs
        if rupees >= 1000:
            lakhs = rupees // 100000
            if lakhs > 0:
                result += _convert_group(lakhs) + ' Lakh '
            rupees = rupees % 100000

        # Handle Thousands
        if rupees >= 1000:
            thousands = rupees // 1000
            if thousands > 0:
                result += _convert_group(thousands) + ' Thousand '
            rupees = rupees % 1000

        # Handle remaining rupees
        if rupees > 0:
            result += _convert_group(rupees)

        result += ' Rupees'

        # Handle paisa
        if paisa > 0:
            result += ' and ' + _convert_group(paisa) + ' Paisa'

        return result.strip()

    allow_payslip_download = fields.Boolean(compute='_compute_allow_payslip_download')

    def _compute_allow_payslip_download(self):
        # Fetch the configuration parameter and ensure it's a string
        allow_download = self.env['ir.config_parameter'].sudo().get_param('hr_payroll.allow_payslip_download',
                                                                          default='False')

        # If it's a string, compare case-insensitively, otherwise cast to bool directly
        allow_download = allow_download.lower() == 'true' if isinstance(allow_download, str) else bool(allow_download)

        # Debugging print statement
        print(f"Allow Payslip Download Computed: {allow_download}")
        current_time = datetime.today().day
        days_limit = int(self.env['ir.config_parameter'].sudo().get_param('hr_payroll.days_allowed', default=10))
        print(f"day_limit: {days_limit}")
        is_admin = self.env.user.has_group('base.group_system') or self.env.user.has_group(
            'om_hr_payroll.group_hr_payroll_manager')
        print(is_admin)

        for record in self:
            record.allow_payslip_download = is_admin or (allow_download and current_time <= days_limit)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False):
        user = self.env.user

        # Get the months allowed for visibility from settings
        months_allowed = int(self.env['ir.config_parameter'].sudo().get_param('hr_payroll.months_allowed', default=3))

        # Check if the user is an admin or payroll manager
        is_admin = user.has_group('base.group_system') or user.has_group('om_hr_payroll.group_hr_payroll_manager')

        if not is_admin:
            # Restrict the employee to only see payslips from the last X months
            today = fields.Date.today()
            limit_date = today - relativedelta(months=months_allowed)

            # Add condition to filter based on the 'date_to' field
            args += [('date_to', '>=', limit_date)]

        # Call the parent search with modified arguments
        return super(HrPayslip, self)._search(args, offset, limit, order, count)

    def action_payslip_done(self):
        return super(HrPayslip, self).action_payslip_done()

    def _compute_details_by_salary_rule_category(self):
        for payslip in self:
            payslip.details_by_salary_rule_category = payslip.mapped('line_ids').filtered(lambda line: line.category_id)

    def _compute_payslip_count(self):
        for payslip in self:
            payslip.payslip_count = len(payslip.line_ids)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(self.filtered(lambda payslip: payslip.date_from > payslip.date_to)):
            raise ValidationError(_("Payslip 'Date From' must be earlier 'Date To'."))

    def action_payslip_draft(self):
        return self.write({'state': 'draft'})

    def print_custom_report(self):
        self.ensure_one()
        # current_time = fields.Datetime.context_timestamp(self, datetime.now())
        # days_limit = int(self.env['ir.config_parameter'].sudo().get_param('hr_payroll.days_allowed', default=10))
        #
        # if current_time.day > days_limit:
        #     raise UserError("You can't download the payslip after the 10th day of the month.")

        # return self.env.ref("om_hr_payroll.action_report_hr_payslip").report_action(self)
        try:
            # Find a customizer record for the payslip model and the correct report template
            customizer = self.env['xml.upload'].search([
                ('model_id.model', '=', 'hr.payslip'),
                ('report_action', '=', 'action_xml_upload_custom_report_format_for_all'),
                ('xml_file', '!=', False),
            ], limit=1)

            # Only use the custom report if a valid customizer record exists and has content
            if customizer and customizer.xml_file:
                return self.env.ref("data_recycle.action_xml_upload_custom_report_format_for_all").report_action(self)
            else:
                # Fallback to the default report if no valid customizer record
                return self.env.ref("om_hr_payroll.action_report_hr_payslip").report_action(self)
        except ValueError:
            # Fallback to the default report if the custom report action is not found (module not installed)
            return self.env.ref("om_hr_payroll.action_report_hr_payslip").report_action(self)

    def action_payslip_done(self):
        self.compute_sheet()
        return self.write({'state': 'done'})

    def action_payslip_cancel(self):
        # if self.filtered(lambda slip: slip.state == 'done'):
        #     raise UserError(_("Cannot cancel a payslip that is done."))
        return self.write({'state': 'cancel'})

    def refund_sheet(self):
        for payslip in self:
            copied_payslip = payslip.copy({'credit_note': True, 'name': _('Refund: ') + payslip.name})
            copied_payslip.compute_sheet()
            copied_payslip.action_payslip_done()
        form_view_ref = self.env.ref('om_om_hr_payroll.view_hr_payslip_form', False)
        tree_view_ref = self.env.ref('om_om_hr_payroll.view_hr_payslip_tree', False)
        return {
            'name': (_("Refund Payslip")),
            'view_mode': 'tree, form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': "[('id', 'in', %s)]" % copied_payslip.ids,
            'views': [(tree_view_ref and tree_view_ref.id or False, 'tree'),
                      (form_view_ref and form_view_ref.id or False, 'form')],
            'context': {}
        }

    def action_send_email(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = self.env.ref('om_hr_payroll.mail_template_payslip').id
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[1]

        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'hr.payslip',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        }
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def check_done(self):
        return True

    def unlink(self):
        if any(self.filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslip, self).unlink()

    # TODO move this function into hr_contract module, on hr.employee object
    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        @param employee: recordset of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        # a contract is valid if it ends between the given dates
        clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]
        # OR if it starts between the given dates
        clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]
        # OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]
        clause_final = [('employee_id', '=', employee.id), ('state', '=', 'open'), '|',
                        '|'] + clause_1 + clause_2 + clause_3
        return self.env['hr.contract'].search(clause_final).ids

    def compute_sheet(self):
        for payslip in self:
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            # delete old payslip lines
            payslip.line_ids.unlink()
            # set the list of contract for which the rules have to be applied
            # if we don't give the contract, then the rules to apply should be for all current contracts of the employee
            current_date = date.today()
            it_declaration_year = str(current_date.strftime('%Y')) + '-' + str(
                (current_date + relativedelta(years=1)).strftime('%y')) if current_date > date(current_date.year, 3,
                                                                                               31) else str(
                (current_date - relativedelta(years=1)).strftime('%Y')) + '-' + str(current_date.strftime('%y'))
            financial_year = self.env['financial.year'].search([('name', '=', it_declaration_year)])

            contract_ids = payslip.contract_id.ids or \
                           self.get_contract(payslip.employee_id, payslip.date_from, payslip.date_to)

            it_declaration_year_record = self.env['it.declaration.payslip'].search(
                [('employee_id', '=', payslip.employee_id.id), ('financial_year', '=', financial_year.id)], limit=1)

            if not it_declaration_year_record:
                raise ValidationError(
                    _("No IT Declaration Found for Year %s Employee Name: %s Or Its Not Locked Yet") % (
                        financial_year.name, payslip.employee_id.name))

            if not contract_ids:
                raise ValidationError(
                    _("No running contract found for the employee: %s or no contract in the given period" % payslip.employee_id.name))
            lines = [(0, 0, line) for line in self._get_payslip_lines(contract_ids, payslip.id)]
            payslip.write({'line_ids': lines, 'number': number})
        return True

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        @param contract: Browse record of contracts
        @return: returns a list of dict containing the input that should be applied
                for the given contract between date_from and date_to
        """
        res = []
        # fill only if the contract as a working schedule linked
        for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):

            # Determine contract effective period (intersection of payslip period and contract period)
            calendar = contract.resource_calendar_id
            tz = timezone(calendar.tz or 'UTC')

            # localize payslip period datetimes to the contract/calendar timezone to avoid
            # comparing offset-naive and offset-aware datetimes
            day_from_naive = datetime.combine(fields.Date.from_string(date_from), time.min)
            day_to_naive = datetime.combine(fields.Date.from_string(date_to), time.max)
            day_from = tz.localize(day_from_naive)
            day_to = tz.localize(day_to_naive)

            contract_start = contract.date_start
            contract_end = contract.date_end

            if contract_start:
                cs = fields.Date.from_string(contract_start) if isinstance(contract_start, str) else contract_start
                contract_start_dt = tz.localize(datetime.combine(cs, time.min))
            else:
                contract_start_dt = None

            if contract_end:
                ce = fields.Date.from_string(contract_end) if isinstance(contract_end, str) else contract_end
                contract_end_dt = tz.localize(datetime.combine(ce, time.max))
            else:
                contract_end_dt = None

            # effective range for this contract
            effective_from = day_from if not contract_start_dt else max(day_from, contract_start_dt)
            effective_to = day_to if not contract_end_dt else min(day_to, contract_end_dt)

            # if the effective period is empty, skip this contract
            if effective_from >= effective_to:
                continue

            # compute leave days within effective period
            leaves = {}
            leave_hours_by_date = {}
            day_leave_intervals = contract.employee_id.list_leaves(
                effective_from,
                effective_to,
                calendar=contract.resource_calendar_id
            )

            for day, hours, leave in day_leave_intervals:
                holiday = leave.holiday_id
                # Skip if holiday status is blank (no leave type)
                if not holiday.holiday_status_id:
                    continue

                current_leave_struct = leaves.setdefault(
                    holiday.holiday_status_id,
                    {
                        'name': holiday.holiday_status_id.name or _('Global Leaves'),
                        'sequence': 5,
                        'code': holiday.holiday_status_id.code or 'GLOBAL',
                        'number_of_days': 0.0,
                        'number_of_hours': 0.0,
                        'contract_id': contract.id,
                    }
                )

                current_leave_struct['number_of_hours'] -= hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )

                if work_hours:
                    current_leave_struct['number_of_days'] -= hours / work_hours

                date_key = day.strftime('%Y-%m-%d')
                leave_hours_by_date[date_key] = leave_hours_by_date.get(date_key, 0) + hours

            # compute worked days for the full payslip period (so the "Normal Working Days" row
            # reflects the whole payslip month). Shortfall/attendance processing below will still
            # be limited to the contract-effective period.
            work_data = contract.employee_id._get_work_days_data(
                day_from,
                day_to,
                calendar=contract.resource_calendar_id,
                compute_leaves=False,
            )

            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': work_data['days'],
                'number_of_hours': work_data['hours'],
                'contract_id': contract.id,
            }

            res.append(attendances)

            # DHRUTI START

            # Get contract start date for filtering
            contract_start_date = contract.date_start
            if contract_start_date:
                contract_start_datetime = tz.localize(datetime.combine(
                    fields.Date.from_string(contract_start_date) if isinstance(contract_start_date,
                                                                               str) else contract_start_date,
                    time.min
                ))
            else:
                contract_start_datetime = None
            # DHRUTI END

            # Get public holidays overlapping the effective period
            public_holidays = self.env['resource.calendar.leaves'].search([
                ('resource_id', '=', False),
                ('company_id', 'in', self.env.companies.ids),
                ('date_from', '<=', effective_to),
                ('date_to', '>=', effective_from),
                '|',
                ('calendar_id', '=', False),
                ('calendar_id', '=', calendar.id),
            ])

            # Calculate public holiday hours by date within the FULL payslip period
            # (not just the contract-effective period). Public holidays reduce expected work
            # but are paid, so they should be included in WORK100 as paid days.
            public_holiday_hours_by_date = {}
            for holiday in public_holidays:
                # Convert holiday datetimes to naive UTC datetimes first (fields.Datetime.context_timestamp
                # expects a naive datetime in UTC which it will then localize). If the value we pass is
                # already tz-aware, normalize it to UTC and then make it naive by removing tzinfo.
                def to_naive_utc(dt):
                    if dt is None:
                        return None
                    # If dt is tz-aware, convert to UTC and drop tzinfo
                    if dt.tzinfo is not None:
                        return dt.astimezone(timezone('UTC')).replace(tzinfo=None)
                    return dt

                holiday_start = to_naive_utc(holiday.date_from)
                holiday_end = to_naive_utc(holiday.date_to)

                day_from_naive = to_naive_utc(day_from)
                day_to_naive = to_naive_utc(day_to)

                # Use fields.Datetime.context_timestamp to convert naive UTC datetimes into the
                # local timezone for comparisons, but ensure inputs are naive.
                holiday_start_ts = fields.Datetime.context_timestamp(self, holiday_start) if holiday_start else None
                holiday_end_ts = fields.Datetime.context_timestamp(self, holiday_end) if holiday_end else None
                day_from_ts = fields.Datetime.context_timestamp(self, day_from_naive) if day_from_naive else None
                day_to_ts = fields.Datetime.context_timestamp(self, day_to_naive) if day_to_naive else None

                # Get the overlap period with the FULL payslip period (not contract-effective)
                overlap_start = max(holiday_start_ts, day_from_ts) if (holiday_start_ts and day_from_ts) else (
                        holiday_start_ts or day_from_ts)
                overlap_end = min(holiday_end_ts, day_to_ts) if (holiday_end_ts and day_to_ts) else (
                        holiday_end_ts or day_to_ts)

                if overlap_start < overlap_end:
                    # Calculate working hours that would be affected by this public holiday
                    current_day = overlap_start.date()
                    while current_day <= overlap_end.date():
                        day_start = tz.localize(datetime.combine(current_day, time.min))
                        day_end = tz.localize(datetime.combine(current_day, time.max))

                        # Get the intersection of holiday period and current day
                        day_holiday_start = max(overlap_start, day_start)
                        day_holiday_end = min(overlap_end, day_end)

                        if day_holiday_start < day_holiday_end:
                            # Calculate how many working hours are affected on this day
                            affected_hours = calendar.get_work_hours_count(
                                day_holiday_start,
                                day_holiday_end,
                                compute_leaves=False,
                            )

                            date_key = current_day.strftime('%Y-%m-%d')
                            if date_key not in public_holiday_hours_by_date:
                                public_holiday_hours_by_date[date_key] = 0
                            public_holiday_hours_by_date[date_key] += affected_hours

                        current_day += timedelta(days=1)

            print(f"Public holiday hours by date: {public_holiday_hours_by_date}")
            print(f"Leave hours by date: {leave_hours_by_date}")

            # Fetch the attendance records within the effective contract period only
            attend_report_ids = self.env['hr.attendance'].search([
                ('employee_id', '=', contract.employee_id.id),
                ('check_in', '>=', effective_from),
                ('check_out', '<=', effective_to)
            ])

            # Calculate actual working hours from attendance, grouped by date
            attendance_by_date = {}
            for attendance in attend_report_ids:
                attendance_date = attendance.check_in.date().strftime('%Y-%m-%d')
                if attendance_date not in attendance_by_date:
                    attendance_by_date[attendance_date] = 0

                actual_worked_hours = round(attendance.worked_hours, 2)
                attendance_by_date[attendance_date] += actual_worked_hours

                print(f"Attendance on {attendance_date}: {actual_worked_hours} hours")

            # Calculate shortfall as: WORK100_days (full payslip) - attendance_days - leave_days - public_holiday_days
            # Public holidays are PAID days (should not count as shortfall).
            # Only attendance after contract start and leaves after contract start count towards worked days.
            # WORK100 is already computed above in work_data (full payslip period).
            daily_expected_hours = contract.resource_calendar_id.hours_per_day

            total_expected_days_full = work_data['days']
            total_attendance_hours = sum(attendance_by_date.values())
            total_attendance_days = total_attendance_hours / daily_expected_hours if daily_expected_hours else 0

            total_leave_hours = sum(leave_hours_by_date.values())
            total_leave_days = total_leave_hours / daily_expected_hours if daily_expected_hours else 0

            total_public_holiday_hours = sum(public_holiday_hours_by_date.values())
            total_public_holiday_days = total_public_holiday_hours / daily_expected_hours if daily_expected_hours else 0

            # Shortfall in days (positive number means missing days)
            # = Expected days - Attended days - Leave days - Public Holiday (paid) days
            total_shortfall_days = total_expected_days_full - total_attendance_days - total_leave_days - total_public_holiday_days
            print('total_shortfall_days', total_shortfall_days)
            # If shortfall is positive (i.e., there are missing days), apply rounding rules and append a SHORTFALL line
            if total_shortfall_days > 0:
                # Apply rounding rules on total
                fractional_part = total_shortfall_days - int(total_shortfall_days)
                if 0 <= fractional_part <= 0.25:
                    total_shortfall_days = int(total_shortfall_days)  # round down
                elif fractional_part >= 0.75:
                    total_shortfall_days = int(total_shortfall_days) + 1  # round up
                else:
                    total_shortfall_days = int(total_shortfall_days) + 0.5

                # Convert back to hours
                total_shortfall_hours = total_shortfall_days * daily_expected_hours

                if not contract.employee_id.disable_tracking:
                    res.append({
                        'name': 'Attendance Shortfall',
                        'sequence': 2,
                        'code': 'SHORTFALL',
                        'number_of_days': -(total_shortfall_days),
                        'number_of_hours': -(total_shortfall_hours),
                        'contract_id': contract.id
                    })

            res.extend(leaves.values())

        return res

    # @api.model
    # def get_worked_day_lines(self, contracts, date_from, date_to):
    #     """
    #     @param contract: Browse record of contracts
    #     @return: returns a list of dict containing the input that should be applied
    #             for the given contract between date_from and date_to
    #     """
    #     res = []
    #     # fill only if the contract as a working schedule linked
    #     for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):
    #         day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
    #         day_to = datetime.combine(fields.Date.from_string(date_to), time.max)
    #
    #         # compute leave days
    #         leaves = {}
    #         leave_hours_by_date = {}
    #         calendar = contract.resource_calendar_id
    #         tz = timezone(calendar.tz)
    #         day_leave_intervals = contract.employee_id.list_leaves(
    #             day_from,
    #             day_to,
    #             calendar=contract.resource_calendar_id
    #         )
    #
    #         for day, hours, leave in day_leave_intervals:
    #             holiday = leave.holiday_id
    #             # Skip if holiday status is blank (no leave type)
    #             if not holiday.holiday_status_id:
    #                 continue
    #
    #             current_leave_struct = leaves.setdefault(
    #                 holiday.holiday_status_id,
    #                 {
    #                     'name': holiday.holiday_status_id.name or _('Global Leaves'),
    #                     'sequence': 5,
    #                     'code': holiday.holiday_status_id.code or 'GLOBAL',
    #                     'number_of_days': 0.0,
    #                     'number_of_hours': 0.0,
    #                     'contract_id': contract.id,
    #                 }
    #             )
    #
    #             current_leave_struct['number_of_hours'] -= hours
    #             work_hours = calendar.get_work_hours_count(
    #                 tz.localize(datetime.combine(day, time.min)),
    #                 tz.localize(datetime.combine(day, time.max)),
    #                 compute_leaves=False,
    #             )
    #
    #             if work_hours:
    #                 current_leave_struct['number_of_days'] -= hours / work_hours
    #
    #             date_key = day.strftime('%Y-%m-%d')
    #             leave_hours_by_date[date_key] = leave_hours_by_date.get(date_key, 0) + hours
    #
    #         # compute worked days
    #         work_data = contract.employee_id._get_work_days_data(
    #             day_from,
    #             day_to,
    #             calendar=contract.resource_calendar_id,
    #             compute_leaves=False,
    #         )
    #
    #         attendances = {
    #             'name': _("Normal Working Days paid at 100%"),
    #             'sequence': 1,
    #             'code': 'WORK100',
    #             'number_of_days': work_data['days'],
    #             'number_of_hours': work_data['hours'],
    #             'contract_id': contract.id,
    #         }
    #
    #         res.append(attendances)
    #
    #         # Get public holidays from resource.calendar.leaves
    #
    #         public_holidays = self.env['resource.calendar.leaves'].search([
    #             ('resource_id', '=', False),
    #             ('company_id', 'in', self.env.companies.ids),
    #             ('date_from', '<=', day_to),
    #             ('date_to', '>=', day_from),
    #             '|',
    #             ('calendar_id', '=', False),
    #             ('calendar_id', '=', calendar.id),
    #         ])
    #
    #         # Calculate public holiday hours by date
    #         public_holiday_hours_by_date = {}
    #         for holiday in public_holidays:
    #             # Convert to employee/calendar timezone
    #             holiday_start = fields.Datetime.context_timestamp(self, holiday.date_from)
    #             holiday_end = fields.Datetime.context_timestamp(self, holiday.date_to)
    #
    #             # Get the overlap period with our date range (already localized)
    #             overlap_start = max(holiday_start, fields.Datetime.context_timestamp(self, day_from))
    #             overlap_end = min(holiday_end, fields.Datetime.context_timestamp(self, day_to))
    #
    #             if overlap_start < overlap_end:
    #                 # Calculate working hours that would be affected by this public holiday
    #                 current_day = overlap_start.date()
    #                 while current_day <= overlap_end.date():
    #                     day_start = tz.localize(datetime.combine(current_day, time.min))
    #                     day_end = tz.localize(datetime.combine(current_day, time.max))
    #
    #                     # Get the intersection of holiday period and current day
    #                     day_holiday_start = max(overlap_start, day_start)
    #                     day_holiday_end = min(overlap_end, day_end)
    #
    #                     if day_holiday_start < day_holiday_end:
    #                         # Calculate how many working hours are affected on this day
    #                         affected_hours = calendar.get_work_hours_count(
    #                             day_holiday_start,
    #                             day_holiday_end,
    #                             compute_leaves=False,
    #                         )
    #
    #                         date_key = current_day.strftime('%Y-%m-%d')
    #                         if date_key not in public_holiday_hours_by_date:
    #                             public_holiday_hours_by_date[date_key] = 0
    #                         public_holiday_hours_by_date[date_key] += affected_hours
    #
    #                     current_day += timedelta(days=1)
    #
    #         print(f"Public holiday hours by date: {public_holiday_hours_by_date}")
    #         print(f"Leave hours by date: {leave_hours_by_date}")
    #
    #         # Fetch the attendance records within the given period
    #         attend_report_ids = self.env['hr.attendance'].search([
    #             ('employee_id', '=', contract.employee_id.id),
    #             ('check_in', '>=', day_from),
    #             ('check_out', '<=', day_to)
    #         ])
    #
    #         # Calculate actual working hours from attendance, grouped by date
    #         attendance_by_date = {}
    #         for attendance in attend_report_ids:
    #             attendance_date = attendance.check_in.date().strftime('%Y-%m-%d')
    #             if attendance_date not in attendance_by_date:
    #                 attendance_by_date[attendance_date] = 0
    #
    #             actual_worked_hours = round(attendance.worked_hours, 2)
    #             attendance_by_date[attendance_date] += actual_worked_hours
    #
    #             print(f"Attendance on {attendance_date}: {actual_worked_hours} hours")
    #
    #         # Calculate expected daily hours for the contract
    #         daily_expected_hours = contract.resource_calendar_id.hours_per_day
    #
    #         # Calculate shortfall DAY BY DAY instead of total period
    #         total_shortfall_hours = 0
    #         total_shortfall_days = 0
    #
    #         current_date = day_from.date()
    #         end_date = day_to.date()
    #
    #         while current_date <= end_date:
    #             date_str = current_date.strftime('%Y-%m-%d')
    #
    #             day_start = tz.localize(datetime.combine(current_date, time.min))
    #             day_end = tz.localize(datetime.combine(current_date, time.max))
    #
    #             expected_hours_for_day = calendar.get_work_hours_count(
    #                 day_start,
    #                 day_end,
    #                 compute_leaves=False,
    #             )
    #
    #             if expected_hours_for_day > 0:
    #                 actual_hours_for_day = attendance_by_date.get(date_str, 0)
    #                 public_holiday_hours_for_day = public_holiday_hours_by_date.get(date_str, 0)
    #                 leave_hours_for_day = leave_hours_by_date.get(date_str, 0)
    #
    #                 adjusted_expected_hours_for_day = (
    #                         expected_hours_for_day
    #                         - public_holiday_hours_for_day
    #                         - leave_hours_for_day
    #                 )
    #
    #                 if adjusted_expected_hours_for_day > actual_hours_for_day:
    #                     daily_shortfall_hours = adjusted_expected_hours_for_day - actual_hours_for_day
    #                     total_shortfall_hours += daily_shortfall_hours
    #                     print(f"Day {date_str}: Shortfall {daily_shortfall_hours} hours")
    #                 else:
    #                     print(f"Day {date_str}: No shortfall")
    #
    #             current_date += timedelta(days=1)
    #
    #         # ---- ROUNDING APPLIED ON TOTAL ----
    #
    #         if total_shortfall_hours > 0:
    #             daily_expected_hours = contract.resource_calendar_id.hours_per_day
    #             total_shortfall_days = total_shortfall_hours / daily_expected_hours
    #
    #             # Apply rounding rules on total
    #             fractional_part = total_shortfall_days - int(total_shortfall_days)
    #             if 0 < fractional_part < 0.25:
    #                 total_shortfall_days = int(total_shortfall_days)  # round down
    #             elif fractional_part >= 0.75:
    #                 total_shortfall_days = int(total_shortfall_days) + 1  # round up
    #             else:
    #                 total_shortfall_days = int(total_shortfall_days) + 0.5
    #
    #             # Adjust hours to match rounded days
    #             total_shortfall_hours = total_shortfall_days * daily_expected_hours
    #
    #             if total_shortfall_days > 0:
    #                 res.append({
    #                     'name': 'Attendance Shortfall',
    #                     'sequence': 2,
    #                     'code': 'SHORTFALL',
    #                     'number_of_days': -(total_shortfall_days),
    #                     'number_of_hours': -(total_shortfall_hours),
    #                     'contract_id': contract.id
    #                 })
    #                 print(f"Total Shortfall: {total_shortfall_days} days, {total_shortfall_hours} hours")
    #             else:
    #                 print("No shortfall after rounding")
    #
    #         res.extend(leaves.values())
    #
    #     return res

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = []

        structure_ids = contracts.get_all_structures()
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]
        inputs = self.env['hr.salary.rule'].browse(sorted_rule_ids).mapped('input_ids')

        for contract in contracts:
            for input in inputs:
                input_data = {
                    'name': input.name,
                    'code': input.code,
                    'contract_id': contract.id,
                }
                res += [input_data]
        return res

    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and \
                                                          localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, employee_id, dict, env):
                self.employee_id = employee_id
                self.dict = dict
                self.env = env

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""
                    SELECT sum(amount) as sum
                    FROM hr_payslip as hp, hr_payslip_input as pi
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s""",
                                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()[0] or 0.0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""
                    SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours
                    FROM hr_payslip as hp, hr_payslip_worked_days as pi
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s""",
                                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute("""SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)
                            FROM hr_payslip as hp, hr_payslip_line as pl
                            WHERE hp.employee_id = %s AND hp.state = 'done'
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s""",
                                    (self.employee_id, from_date, to_date, code))
                res = self.env.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules_dict = {}
        worked_days_dict = {}
        inputs_dict = {}
        blacklist = []
        payslip = self.env['hr.payslip'].browse(payslip_id)
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days_dict[worked_days_line.code] = worked_days_line
        for input_line in payslip.input_line_ids:
            inputs_dict[input_line.code] = input_line

        categories = BrowsableObject(payslip.employee_id.id, {}, self.env)
        inputs = InputLine(payslip.employee_id.id, inputs_dict, self.env)
        worked_days = WorkedDays(payslip.employee_id.id, worked_days_dict, self.env)
        payslips = Payslips(payslip.employee_id.id, payslip, self.env)
        rules = BrowsableObject(payslip.employee_id.id, rules_dict, self.env)

        baselocaldict = {'categories': categories, 'rules': rules, 'payslip': payslips, 'worked_days': worked_days,
                         'inputs': inputs}
        # get the ids of the structures on the contracts and their parent id as well
        contracts = self.env['hr.contract'].browse(contract_ids)
        if len(contracts) == 1 and payslip.struct_id:
            structure_ids = list(set(payslip.struct_id._get_parent_structure().ids))
        else:
            structure_ids = contracts.get_all_structures()
        # get the rules of the structure and thier children
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]
        sorted_rules = self.env['hr.salary.rule'].browse(sorted_rule_ids)

        for contract in contracts:
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in sorted_rules:
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if rule._satisfy_condition(localdict) and rule.id not in blacklist:
                    # compute the amount of the rule
                    amount, qty, rate = rule._compute_rule(localdict)
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = contract.company_id.currency_id.round(amount * qty * rate / 100.0)
                    localdict[rule.code] = tot_rule
                    rules_dict[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in rule._recursive_search_of_rules()]

        return list(result_dict.values())

    # YTI TODO To rename. This method is not really an onchange, as it is not in any view
    # employee_id and contract_id could be browse records
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        # defaults
        res = {
            'value': {
                'line_ids': [],
                # delete old input lines
                'input_line_ids': [(2, x,) for x in self.input_line_ids.ids],
                # delete old worked days lines
                'worked_days_line_ids': [(2, x,) for x in self.worked_days_line_ids.ids],
                # 'details_by_salary_head':[], TODO put me back
                'name': '',
                'contract_id': False,
                'struct_id': False,
            }
        }
        if (not employee_id) or (not date_from) or (not date_to):
            return res
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        employee = self.env['hr.employee'].browse(employee_id)
        locale = self.env.context.get('lang') or 'en_US'
        res['value'].update({
            'name': _('Salary Slip of %s for %s') % (
                employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
            'company_id': employee.company_id.id,
        })

        if not self.env.context.get('contract'):
            # fill with the first contract of the employee
            contract_ids = self.get_contract(employee, date_from, date_to)
        else:
            if contract_id:
                # set the list of contract for which the input have to be filled
                contract_ids = [contract_id]
            else:
                # if we don't give the contract, then the input to fill should be for all current contracts of the employee
                contract_ids = self.get_contract(employee, date_from, date_to)

        if not contract_ids:
            return res
        contract = self.env['hr.contract'].browse(contract_ids[0])
        res['value'].update({
            'contract_id': contract.id
        })
        struct = contract.struct_id
        if not struct:
            return res
        res['value'].update({
            'struct_id': struct.id,
        })
        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        res['value'].update({
            'worked_days_line_ids': worked_days_line_ids,
            'input_line_ids': input_line_ids,
        })
        return res

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        self.ensure_one()
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get('lang') or 'en_US'
        self.name = _('Salary Slip of %s for %s') % (
            employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id

        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        if contracts:
            worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
            worked_days_lines = self.worked_days_line_ids.browse([])
            for r in worked_days_line_ids:
                worked_days_lines += worked_days_lines.new(r)
            self.worked_days_line_ids = worked_days_lines

            input_line_ids = self.get_inputs(contracts, date_from, date_to)
            input_lines = self.input_line_ids.browse([])
            for r in input_line_ids:
                input_lines += input_lines.new(r)
            self.input_line_ids = input_lines
            return

    @api.onchange('contract_id')
    def onchange_contract(self):
        if not self.contract_id:
            self.struct_id = False
        self.with_context(contract=True).onchange_employee()
        return

    def get_salary_line_total(self, code):
        self.ensure_one()
        line = self.line_ids.filtered(lambda line: line.code == code)
        if line:
            return line[0].total
        else:
            return 0.0


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _inherit = 'hr.salary.rule'
    _description = 'Payslip Line'
    _order = 'contract_id, sequence'

    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True, index=True)
    rate = fields.Float(string='Rate (%)', default=100.0)
    amount = fields.Float()
    quantity = fields.Float(default=1.0)
    total = fields.Float(compute='_compute_total', string='Total')

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'employee_id' not in values or 'contract_id' not in values:
                payslip = self.env['hr.payslip'].browse(values.get('slip_id'))
                values['employee_id'] = values.get('employee_id') or payslip.employee_id.id
                values['contract_id'] = values.get('contract_id') or payslip.contract_id and payslip.contract_id.id
                if not values['contract_id']:
                    raise UserError(_('You must set a contract to create a payslip line.'))
        return super(HrPayslipLine, self).create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
                                  help="The contract for which applied this input")


class HrPayslipInput(models.Model):
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
                                  help="The contract for which applied this input")


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _description = 'Payslip Batches'

    name = fields.Char(required=True)
    slip_ids = fields.One2many('hr.payslip', 'payslip_run_id', string='Payslips')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('close', 'Close'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    date_start = fields.Date(
        string='Date From', required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1))
    )
    date_end = fields.Date(
        string='Date To', required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date())
    )
    credit_note = fields.Boolean(
        string='Credit Note',
        help="If its checked, indicates that all payslips generated from here are refund payslips."
    )

    def draft_payslip_run(self):
        return self.write({'state': 'draft'})

    def close_payslip_run(self):
        return self.write({'state': 'close'})

    def done_payslip_run(self):
        for line in self.slip_ids:
            line.action_payslip_done()
        return self.write({'state': 'done'})

    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise ValidationError(_('You Cannot Delete Done Payslips Batches'))
        return super(HrPayslipRun, self).unlink()
