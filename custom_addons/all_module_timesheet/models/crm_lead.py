from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    timesheet_ids = fields.One2many(
        comodel_name='account.analytic.line',
        compute='_compute_timesheet_ids',
        string='Timesheets',
        store=False
    )

    def _compute_timesheet_ids(self):
        for record in self:
            record.timesheet_ids = self.env['account.analytic.line'].search([
                ('source_model', '=', 'crm.lead'),
                ('source_record_id', '=', record.id)
            ])

    can_start_timer = fields.Boolean(
        string='Can Start Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )
    can_stop_timer = fields.Boolean(
        string='Can Stop Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )

    @api.depends_context('uid')
    def _compute_timer_button_visibility(self):
        for lead in self:
            user_timer = self.env['account.analytic.line'].search([
                ('source_model', '=', 'crm.lead'),
                ('source_record_id', '=', lead.id),
                ('user_id', '=', self.env.user.id),
            ])
            running = user_timer.filtered(lambda t: t.is_timer_running)

            # Default all actions to False
            lead.can_start_timer = False
            lead.can_stop_timer = False

            if not running:
                lead.can_start_timer = True
            else:
                lead.can_stop_timer = True

    def action_start_lead_timer(self):
        self.ensure_one()

        # Restriction: Lead must be assigned
        if not self.user_id:
            raise ValidationError("This Lead/Opportunity is not assigned to any salesperson.")

        # Restriction: Only the assigned user can start the timer
        if self.user_id != self.env.user:
            raise ValidationError("Only the assigned salesperson can start the work.")

        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True)
        ], limit=1)

        if running_timer:
            raise ValidationError(f"You already have a running timer: {running_timer.name}")

        default_category = self.env['custom.timesheet.category'].search([('code', '=', 'CRM')], limit=1)
        if not default_category:
            raise ValidationError("Please define at least one CRM timesheet category.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)
        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        timesheet = self.env['account.analytic.line'].create({
            'name': f'Lead/Opportunity: {self.name}',
            'user_id': self.env.user.id,
            'category_id': default_category.id,
            'employee_id': self.env.user.employee_id.id,
            'source_model': 'crm.lead',
            'source_record_id': self.id,
            'start_latitude': latitude,
            'start_longitude': longitude,
            'start_address': address,
        })

        # --- Create GPS Tracking Point (CALL START) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_start',
                address=address,
                source_model='crm.lead',
                source_record_id=self.id,
            )

        return timesheet.action_start_timer()

    def action_stop_lead_timer(self):
        self.ensure_one()

        # Restriction: Lead must be assigned
        if not self.user_id:
            raise ValidationError("This Lead/Opportunity is not assigned to any salesperson.")

        # Restriction: Only the assigned user can start the timer
        if self.user_id != self.env.user:
            raise ValidationError("Only the assigned salesperson can stop the work.")

        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('source_model', '=', 'crm.lead'),
            ('source_record_id', '=', self.id),
        ], limit=1)

        if not running_timer:
            raise ValidationError("No running timer found for this lead.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)
        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        running_timer.write({
            'end_latitude': latitude,
            'end_longitude': longitude,
            'end_address': address,
        })

        # --- Create GPS Tracking Point (CALL END) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_end',
                address=address,
                source_model='crm.lead',
                source_record_id=self.id,
            )

        return running_timer.action_stop_timer()

    def write(self, vals):
        # Perform actual write operation first
        result = super().write(vals)
        for lead in self:
            # ✅ Update timesheet names if task name has changed
            if 'name' in vals:
                self.env['account.analytic.line'].search(
                    [('source_model', '=', 'crm.lead'), ('source_record_id', '=', lead.id)]).write(
                    {'name': f'Lead/Opportunity: {lead.name}'})

        return result
