from datetime import datetime, time, date, timedelta

import pytz

from odoo import models, fields, api
from odoo.fields import Datetime


class DailyActivityReport(models.Model):
    # _name = 'daily.activity.report'
    # _description = 'Daily Activity Report'
    # _auto = False
    _inherit = 'account.analytic.line'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    category_id = fields.Many2one('custom.timesheet.category', string='Category')

    total_duration_done_resolved = fields.Float(
        string="Total Duration(Creation-Last Checkout)",
        compute='_compute_total_duration_done_resolved',
        store=False
    )

    customer_name = fields.Char(string="Customer Name", compute="_compute_customer_info", store=True)
    customer_mobile = fields.Char(string="Mobile", compute="_compute_customer_info", store=True)
    customer_state = fields.Char(string="Customer State", compute="_compute_customer_info", store=True)
    customer_city = fields.Char(string="Customer City", compute="_compute_customer_info", store=True)
    #distance_km = fields.Float(string="Distance (KM)", compute="_compute_distance_km", store=True)

    name = fields.Char(string="Name", compute=False)
    unit_amount = fields.Float(string="Total Check-In/Out Difference", compute=False)

    checkin_coordinates = fields.Char(string="Check-In Lat/Long", compute="_compute_coordinates", store=True)
    checkout_coordinates = fields.Char(string="Check-Out Lat/Long", compute="_compute_coordinates", store=True)

    @api.depends('start_latitude', 'start_longitude', 'end_latitude', 'end_longitude')
    def _compute_coordinates(self):
        for line in self:
            line.checkin_coordinates = (
                f"{line.start_latitude}, {line.start_longitude}"
                if line.start_latitude and line.start_longitude else ""
            )
            line.checkout_coordinates = (
                f"{line.end_latitude}, {line.end_longitude}"
                if line.end_latitude and line.end_longitude else ""
            )

    @api.depends('source_model', 'source_record_id', 'end_date_time')
    def _compute_total_duration_done_resolved(self):
        for rec in self:
            duration = 0.0
            if rec.source_model == 'project.task' and rec.source_record_id and rec.end_date_time:
                task = rec.env['project.task'].browse(rec.source_record_id)
                if task.exists():
                    # Calculate duration from creation to this entry's end time
                    duration = rec._calculate_single_duration(
                        task.create_date,
                        rec.end_date_time,
                        task.id
                    )
                    # Only show duration in last entry
                    if not rec._is_last_timesheet_for_task(task):
                        duration = 0.0

            # Add this block for lead/opportunity handling
            elif rec.source_model == 'crm.lead' and rec.source_record_id and rec.end_date_time:
                lead = rec.env['crm.lead'].browse(rec.source_record_id)
                if lead.exists():
                    # Calculate duration from lead creation to this entry's end time
                    duration = rec._calculate_single_duration(
                        lead.create_date,
                        rec.end_date_time,
                        lead.id
                    )
                    # Only show duration in last entry
                    if not rec._is_last_timesheet_for_lead(lead):
                        duration = 0.0

            rec.total_duration_done_resolved = duration

    def _calculate_fsm_duration(self, task):
        """Calculate duration for FSM tasks (Service Calls)"""
        duration = 0.0
        if task.create_date:
            # Only calculate if this is the last timesheet entry
            if self._is_last_timesheet_for_task(task):
                duration = self._calculate_single_duration(
                    task.create_date,
                    self.end_date_time,
                    task.id
                )
        return duration

    def _calculate_regular_task_duration(self, task):
        """Calculate duration for regular project tasks"""
        duration = 0.0
        if task.create_date:
            # For regular tasks, calculate from creation to this entry's end time
            duration = self._calculate_single_duration(
                task.create_date,
                self.end_date_time,
                task.id
            )
        return duration

    def _calculate_lead_duration(self, lead_id):
        """Calculate duration for leads/opportunities"""
        duration = 0.0
        lead = self.env['crm.lead'].browse(lead_id)
        if lead.exists() and lead.create_date:
            duration = self._calculate_single_duration(
                lead.create_date,
                self.end_date_time,
                lead.id
            )
        return duration

    def _is_last_timesheet_for_lead(self, lead):
        """Check if this is the last timesheet entry for the lead"""
        newer_entries = self.env['account.analytic.line'].search_count([
            ('source_model', '=', 'crm.lead'),
            ('source_record_id', '=', lead.id),
            '|', ('date', '>', self.date),
            '&', ('date', '=', self.date),
            ('id', '>', self.id)
        ])
        return newer_entries == 0
    def _is_last_timesheet_for_task(self, task):
        """Check if this is the last timesheet entry for the task"""
        # Find if any newer entries exist
        newer_entries = self.env['account.analytic.line'].search_count([
            ('task_id', '=', task.id),
            '|', ('date', '>', self.date),
            '&', ('date', '=', self.date),
            ('id', '>', self.id)
        ])
        return newer_entries == 0

    def _calculate_single_duration(self, start_dt, end_dt, record_id):
        """Generic duration calculation between two datetimes"""
        if not start_dt or not end_dt:
            return 0.0

        try:
            start_dt = self._ensure_datetime(start_dt)
            end_dt = self._ensure_datetime(end_dt)

            if start_dt > end_dt:
                return 0.0

            return round((end_dt - start_dt).total_seconds() / 3600, 2)
        except Exception as e:
            print(f"Duration calculation error for record {record_id}: {str(e)}")
            return 0.0

    def _ensure_datetime(self, dt_value, is_end_date=False):
        """Convert date or datetime to timezone-aware datetime"""
        if not dt_value:
            return None

        user_tz = self.env.user.tz or 'UTC'

        if isinstance(dt_value, datetime):
            if dt_value.tzinfo is None:
                return pytz.UTC.localize(dt_value).astimezone(pytz.timezone(user_tz))
            return dt_value.astimezone(pytz.timezone(user_tz))

        if isinstance(dt_value, date):
            if is_end_date:
                return pytz.timezone(user_tz).localize(datetime.combine(dt_value, time.max))
            return pytz.timezone(user_tz).localize(datetime.combine(dt_value, time.min))

        return None

    @api.depends('source_model', 'source_record_id')
    def _compute_customer_info(self):
        for rec in self:
            name = mobile = state = city = ''
            if rec.source_model == 'project.task' and rec.source_record_id:
                task = rec.env['project.task'].browse(rec.source_record_id)
                if task.exists():
                    if getattr(task, 'is_fsm', False):  # Service Call
                        if task.partner_id:
                            name = task.partner_id.name or ''
                            mobile = task.partner_id.mobile or task.partner_id.phone or ''
                            state = task.partner_id.state_id.name or ''
                            city = task.partner_id.city or ''
                    else:  # Regular Task
                        name = mobile = state = city = 'N/A'
            elif rec.source_model == 'crm.lead' and rec.source_record_id:
                lead = rec.env['crm.lead'].browse(rec.source_record_id)
                if lead.exists() and lead.partner_id:
                    name = lead.partner_id.name or ''
                    mobile = lead.partner_id.mobile or lead.partner_id.phone or ''
                    state = lead.partner_id.state_id.name or ''
                    city = lead.partner_id.city or ''
            rec.customer_name = name
            rec.customer_mobile = mobile
            rec.customer_state = state
            rec.customer_city = city

    def action_open_map_view(self):
        self.ensure_one()
        # Example: open Google Maps in a new tab
        if self.start_latitude and self.start_longitude:
            url = f"https://www.google.com/maps?q={self.start_latitude},{self.start_longitude}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            # Optionally, show a warning if no coordinates
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ir.actions.act_window',
                'view_mode': 'form',
                'target': 'new',
                'name': 'No Location Data',
            }

    # def _compute_distance_km(self):
    #     from math import radians, cos, sin, asin, sqrt
    #     for rec in self:
    #         if rec.start_latitude and rec.start_longitude and rec.end_latitude and rec.end_longitude:
    #             # Haversine formula
    #             lon1, lat1, lon2, lat2 = map(radians, [rec.start_longitude, rec.start_latitude, rec.end_longitude, rec.end_latitude])
    #             dlon = lon2 - lon1
    #             dlat = lat2 - lat1
    #             a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    #             c = 2 * asin(sqrt(a))
    #             r = 6371  # Radius of earth in kilometers
    #             rec.distance_km = round(c * r, 2)
    #         else:
    #             rec.distance_km = 0.0
