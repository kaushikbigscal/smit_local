from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo import fields, models
import requests
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    minimum_timesheet_duration = fields.Float(
        string="Minimum Timesheet Duration (minutes)"
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('account_analytic_line.minimum_timesheet_duration',
                                                  str(self.minimum_timesheet_duration)
                                                  )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config_parameter = self.env['ir.config_parameter'].sudo()
        minimum_duration = float(config_parameter.get_param('account_analytic_line.minimum_timesheet_duration'))
        res.update(minimum_timesheet_duration=minimum_duration)
        return res


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"
    _order = "date_time desc"

    end_time_name = fields.Char(comodel_name='hr.timesheet.switch', string="End Description")

    # -------------------------------------------------custom-----------------------------------------------
    actual_problem = fields.Char(comodel_name='hr.timesheet.switch', string="Actual Problem")
    problem_solution = fields.Char(comodel_name='hr.timesheet.switch', string="Problem Solution")

    latitude = fields.Float(comodel_name='hr.timesheet.switch', string="Latitude", digits=(16, 8))
    longitude = fields.Float(comodel_name='hr.timesheet.switch', string="Longitude", digits=(16, 8))
    location_name = fields.Char(comodel_name='hr.timesheet.switch', string="Location Name",
                                compute='_compute_location_name', store=True)
    # date_time = fields.Datetime(string="Start Date-Time", required=True, default=fields.Datetime.now)
    end_date_time = fields.Datetime(string="End Date-Time", compute="_compute_end_date_time",
                                    inverse="_inverse_end_date_time")
    unit_amount = fields.Float(string="Duration", required=True, default=0.0)

    @api.depends("date_time", "unit_amount")
    def _compute_end_date_time(self):
        """Compute End Date-Time based on Start Date-Time and Duration."""
        for record in self:
            if record.date_time and record.unit_amount:
                record.end_date_time = record.date_time + timedelta(hours=record.unit_amount)
            else:
                record.end_date_time = False

    def _inverse_end_date_time(self):
        """Recalculate unit_amount when End Date-Time is manually changed."""
        for record in self:
            if record.date_time and record.end_date_time:
                duration = (record.end_date_time - record.date_time).total_seconds() / 3600
                _logger.info(f"Calculated duration: {duration} hours")
                record.unit_amount = duration

    @api.depends('latitude', 'longitude')
    def _compute_location_name(self):
        for record in self:
            if record.latitude and record.longitude:
                try:
                    # Add User-Agent header to avoid being blocked
                    headers = {
                        'User-Agent': 'Odoo Timesheet Application'
                    }

                    url = f"https://nominatim.openstreetmap.org/reverse"
                    params = {
                        'format': 'json',
                        'lat': record.latitude,
                        'lon': record.longitude,
                        'zoom': 18,
                        'addressdetails': 1
                    }

                    response = requests.get(url, params=params, headers=headers)

                    if response.status_code == 200:
                        data = response.json()

                        # Extract address components
                        address = data.get('display_name', {})

                        if address:
                            record.location_name = address
                        else:
                            record.location_name = data.get('display_name', 'Location Not Found')
                    else:
                        record.location_name = 'Location Not Found'

                except Exception as e:
                    record.location_name = 'Error Getting Location Name'
            else:
                record.location_name = False

    # @api.depends('latitude', 'longitude')
    # def _compute_location_name(self):
    #
    #     api_key = "MtfiIOJ59AGn4W3BewXyDBNoSLxmGutRIJbx2YHf"  # Replace with your actual API key
    #     for record in self:
    #         if record.latitude and record.longitude:
    #             try:
    #                 headers = {
    #                     'User-Agent': 'Odoo Application'
    #                 }
    #                 url = "https://api.olamaps.io/places/v1/reverse-geocode"
    #
    #                 params = {
    #                     'latlng': f"{record.latitude},{record.longitude}",
    #                     'api_key': api_key
    #                 }
    #
    #                 response = requests.get(url, params=params, headers=headers)
    #                 if response.status_code == 200:
    #                     data = response.json()
    #                     # Extract the formatted_address from the response
    #                     results = data.get('results', [])
    #                     if results:
    #                         formatted_address = results[0].get('formatted_address', 'Location Not Found')
    #                         record.location_name = formatted_address
    #                     else:
    #                         record.location_name = 'Location Not Found'
    #                 else:
    #                     record.location_name = 'Location Not Found'
    #
    #             except Exception as e:
    #                 record.location_name = f"Error: {str(e)}"
    #         else:
    #             record.location_name = False

    # -------------------------------------------------custom-----------------------------------------------

    date_time = fields.Datetime(
        string="Start Time", default=fields.Datetime.now, copy=False
    )
    date_time_end = fields.Datetime(
        string="End Time",
        compute="_compute_date_time_end",
        inverse="_inverse_date_time_end",
    )
    show_time_control = fields.Selection(
        selection=[("resume", "Resume"), ("stop", "Stop")],
        compute="_compute_show_time_control",
        help="Indicate which time control button to show, if any.",
    )
    # Added New
    minimum_duration = fields.Float(
        string="Minimum Duration (minutes)",
        compute='_compute_minimum_duration',
        help="Minimum duration before work can be stopped",
        readonly=False,
        invisible=True
    )
    # Added New
    can_stop_work = fields.Boolean(
        compute="_compute_can_stop_work",
        help="Indicates if enough time has passed to stop work"
    )

    @api.depends()
    def _compute_minimum_duration(self):
        param = self.env['ir.config_parameter'].sudo()
        min_duration = float(param.get_param('account_analytic_line.minimum_timesheet_duration'))

        for record in self:
            record.minimum_duration = min_duration

    @api.depends("date_time", "minimum_duration")
    def _compute_can_stop_work(self):
        now = fields.Datetime.now()
        for record in self:
            if record.date_time:
                min_end_time = record.date_time + timedelta(minutes=record.minimum_duration)
                record.can_stop_work = now >= min_end_time
            else:
                record.can_stop_work = False

    @api.depends("date_time", "unit_amount", "product_uom_id")
    def _compute_date_time_end(self):
        hour_uom = self.env.ref("uom.product_uom_hour")
        for record in self:
            if (
                    record.product_uom_id == hour_uom
                    and record.date_time
                    and record.unit_amount
            ):
                record.date_time_end = record.date_time + relativedelta(
                    hours=record.unit_amount
                )
            else:
                record.date_time_end = record.date_time_end

    def _inverse_date_time_end(self):
        hour_uom = self.env.ref("uom.product_uom_hour")
        for record in self.filtered(lambda x: x.date_time and x.date_time_end):
            if record.product_uom_id == hour_uom:
                record.unit_amount = (
                                             record.date_time_end - record.date_time
                                     ).seconds / 3600

    @api.model
    def _eval_date(self, vals):
        if vals.get("date_time"):
            return dict(vals, date=self._convert_datetime_to_date(vals["date_time"]))
        return vals

    def _convert_datetime_to_date(self, datetime_):
        if isinstance(datetime_, str):
            datetime_ = fields.Datetime.from_string(datetime_)
        return fields.Date.context_today(self, datetime_)

    @api.model
    def _running_domain(self):
        """Domain to find running timesheet lines."""
        return [
            ("date_time", "!=", False),
            ("user_id", "=", self.env.user.id),
            ("project_id.allow_timesheets", "=", True),
            ("unit_amount", "=", 0),
        ]

    @api.model
    def _duration(self, start, end):
        """Compute float duration between start and end."""
        try:
            return (end - start).total_seconds() / 3600
        except TypeError:
            return 0

    @api.depends("employee_id", "unit_amount")
    def _compute_show_time_control(self):
        """Decide when to show time controls."""
        for one in self:
            if one.employee_id not in self.env.user.employee_ids:
                one.show_time_control = False
            elif one.unit_amount or not one.date_time:
                one.show_time_control = "resume"
            else:
                one.show_time_control = "stop"

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(list(map(self._eval_date, vals_list)))

    def write(self, vals):
        return super().write(self._eval_date(vals))

    def action_start_work(self):
        for task in self:
            self.env['account.analytic.line'].create({
                'name': 'Work started on: %s' % task.name,
                'task_id': task.id,
                'project_id': task.project_id.id,
                'user_id': self.env.uid,
                'date': fields.Date.today(),
                'unit_amount': 0.0,
                'employee_id': self.env.user.employee_id.id,
            })
        return True

    def action_stop_work(self):
        for task in self:
            analytic_line = self.env['account.analytic.line'].search([
                ('task_id', '=', task.id),
                ('user_id', '=', self.env.uid),
                ('date', '=', fields.Date.today()),
                ('unit_amount', '<=', 0.01),
            ], limit=1)

            if analytic_line:
                start_time = task.date_time or fields.Datetime.now()
                end_time = fields.Datetime.now()
                duration = (end_time - start_time).total_seconds() / 3600.0
                duration = round(duration, 2)

                analytic_line.write({
                    'name': analytic_line.name + ' | Work stopped',
                    'unit_amount': duration,
                    'end_date_time': end_time
                })
                task.end_date_time = end_time
            else:
                print(f"[DEBUG] No matching analytic line found for task {task.name}")
            return True

    def button_resume_work(self):
        """Create a new record starting now, with a running timer."""
        return {
            "name": _("Resume work"),
            "res_model": "hr.timesheet.switch",
            "target": "new",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "view_type": "form",
        }
