from odoo import models, api, fields
import requests
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    category_id = fields.Many2one(
        'custom.timesheet.category',
        string='Category',
        required=True,
        tracking=True
    )
    is_fsm = fields.Boolean(string='FSM', related='project_id.is_fsm')

    # Generic reference fields for linking to any record
    source_model = fields.Char(
        string='Source Model',
        help='Technical field to store the model name of the linked record'
    )

    source_record_id = fields.Integer(
        string='Source Record ID',
        help='Technical field to store the ID of the linked record'
    )

    source_record_name = fields.Char(
        string='Source Record',
        compute='_compute_source_record_name',
        store=True,
        help='Display name of the linked record'
    )

    date_time = fields.Datetime(
        string="Start Time", default=fields.Datetime.now, copy=False
    )

    end_date_time = fields.Datetime(
        string="End Time",
        compute="_compute_end_date_time",
        inverse="_inverse_end_date_time",
    )

    is_timer_running = fields.Boolean(
        string='Timer Running',
        default=False,
        tracking=True
    )

    start_latitude = fields.Float(string="Start Latitude", digits=(16, 8))
    start_longitude = fields.Float(string="Start Longitude", digits=(16, 8))
    start_address = fields.Char(string="Start Address")

    end_latitude = fields.Float(string="End Latitude", digits=(16, 8))
    end_longitude = fields.Float(string="End Longitude", digits=(16, 8))
    end_address = fields.Char(string="End Address")

    @api.model
    def get_address_from_coordinates(self, latitude, longitude):
        if latitude and longitude:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
            try:
                response = requests.get(url, headers={'User-Agent': 'Effezient Timesheet Agent'})
                response.raise_for_status()
                data = response.json()
                address = data.get('display_name', 'Address not found')
                return address
            except requests.RequestException as e:
                address = f"Error fetching address: {str(e)}"
                return address

    @api.depends('source_model', 'source_record_id')
    def _compute_source_record_name(self):
        for record in self:
            if record.source_model and record.source_record_id:
                try:
                    source_record = self.env[record.source_model].browse(record.source_record_id)
                    if source_record.exists():
                        record.source_record_name = source_record.display_name
                    else:
                        record.source_record_name = f'[Deleted] {record.source_model}#{record.source_record_id}'
                except:
                    record.source_record_name = f'{record.source_model}#{record.source_record_id}'
            else:
                record.source_record_name = ''

    @api.depends("date_time", "unit_amount")
    def _compute_end_date_time(self):
        hour_uom = self.env.ref("uom.product_uom_hour")
        for record in self:
            if (
                    record.product_uom_id == hour_uom
                    and record.date_time
                    and record.unit_amount
            ):
                record.end_date_time = record.date_time + relativedelta(
                    hours=record.unit_amount
                )
            else:
                record.end_date_time = record.end_date_time

    def _inverse_end_date_time(self):
        hour_uom = self.env.ref("uom.product_uom_hour")
        for record in self.filtered(lambda x: x.date_time and x.end_date_time):
            if record.product_uom_id == hour_uom:
                record.unit_amount = (record.end_date_time - record.date_time).seconds / 3600

    def action_start_timer(self):
        """Start the timer for this entry"""
        # Check if user has another running timer
        running_timer = self.search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('id', '!=', self.id)
        ])

        if running_timer:
            raise ValidationError(f'You already have a running timer for: {running_timer.name}. Please stop it first.')

        self.write({
            'date_time': fields.Datetime.now(),
            'end_date_time': False,
            'is_timer_running': True,
            'date': fields.Date.context_today(self),
        })
        return {"type": "ir.actions.act_window_close"}

    def action_stop_timer(self):
        """Stop the timer for this entry"""
        if not self.is_timer_running:
            raise ValidationError('The timer is not running for this entry.')
        if not self.date_time:
            raise ValidationError('Start time is not set. Cannot stop the timer.')

        now = fields.Datetime.now()
        time_diff = now - self.date_time
        total_minutes = time_diff.total_seconds() / 60

        # Fetch the minimum timesheet duration from system parameters
        min_duration_param = self.env['ir.config_parameter'].sudo().get_param(
            'account_analytic_line.minimum_timesheet_duration', default='0')
        min_duration = float(min_duration_param or 0)

        # Check against minimum duration
        if total_minutes < min_duration:
            raise ValidationError(
                f"You must run the timer for at least {min_duration} minutes before stopping it.\n"
                f"Currently logged time: {round(total_minutes, 2)} minutes.")

        hours = time_diff.total_seconds() / 3600

        # Step 1: Temporarily assign a project if missing (Community requires it)
        temp_project = None
        if not self.project_id:
            temp_project = self.env['project.project'].search([], limit=1)
            if temp_project:
                self.project_id = temp_project.id

        self.write({
            'end_date_time': now,
            'unit_amount': hours,
            'is_timer_running': False,
        })

        # Step 3: Remove the temp project if we added one
        if temp_project:
            self.project_id = False

        return {"type": "ir.actions.act_window_close"}
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'reload'
        # }


class TimesheetsAnalysisReport(models.Model):
    _inherit = "timesheets.analysis.report"

    category_id = fields.Many2one(
        'custom.timesheet.category',
        string='Category',
        readonly=True
    )
