# -*- coding: utf-8 -*-

from odoo import Command, models, api, _, fields
from odoo.exceptions import AccessError


class ResCompany(models.Model):
    _name = 'res.company'
    _inherit = 'res.company'

    def _get_field_service_project_values(self):
        project_name = _("Service Call")
        stage_ids = self.env['ir.model.data'].sudo().search_read(
            [('module', '=', 'industry_fsm'), ('name', 'like', 'planning_project_stage_')], ['res_id'])
        type_ids = [Command.link(stage_id['res_id']) for stage_id in stage_ids]
        return [{
            'name': project_name,
            'is_fsm': True,
            'allow_timesheets': True,
            'type_ids': type_ids,
            'company_id': company.id

        } for company in self]

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        self.env['project.project'].sudo().create(companies._get_field_service_project_values())
        return companies

    resolved_required_fields = fields.Many2many(
        'ir.model.fields',
        string="Required Fields for Resolved Stage",
        domain=[('model', 'in', ['project.task', 'end.service.call.wizard'])],
        help="Select the fields that must be filled before moving to the 'Resolved' stage."
    )
    attachment_required = fields.Boolean(string="Attachment Required",
                                         config_parameter="industry_fsm.attachment_required")

    signed_required = fields.Boolean(string="Signature Required")
    
    
    enable_geofencing_on_checkin = fields.Boolean(
        string="Enable Geofencing On Check In", default=False,
        help="Restrict check-in based on location distance from customer."
    )
    enable_geofencing_on_checkout = fields.Boolean(
        string="Enable Geofencing On Check Out", default=False,
        help="Restrict check-out based on location distance from customer."
    )
    allowed_distance_service = fields.Float(
        string='Allowed Distance (M)', digits=(16, 2),
        help='Maximum distance (Meter) allowed from customer location for check-in/out.'
    )

    @api.onchange("enable_geofencing_on_checkin", "enable_geofencing_on_checkout")
    def _onchange_geo_flags(self):
        if not self.enable_geofencing_on_checkin and not self.enable_geofencing_on_checkout:
            self.allowed_distance_service = 0.0

    def write(self, vals):
        checkin = vals.get("enable_geofencing_on_checkin", self.enable_geofencing_on_checkin)
        checkout = vals.get("enable_geofencing_on_checkout", self.enable_geofencing_on_checkout)
        distance = vals.get("allowed_distance_service", self.allowed_distance_service)

        if (checkin or checkout) and distance <= 0:
            raise AccessError(_("Allowed distance must be set if geofencing is enabled."))

        return super().write(vals)
