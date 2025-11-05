# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_industry_fsm_report = fields.Boolean("Worksheets")
    module_industry_fsm_sale = fields.Boolean(
        string="Time and Material Invoicing",
        compute='_compute_module_industry_fsm_sale',
        store=True,
        readonly=False)
    group_industry_fsm_quotations = fields.Boolean(
        string="Extra Quotations",
        implied_group="industry_fsm.group_fsm_quotation_from_task",
        compute='_compute_group_industry_fsm_quotations',
        store=True,
        readonly=False)
    service_call_dependencies = fields.Boolean(
        string="Call Dependencies",
        config_parameter="industry_fsm.service_call_dependencies",
        help="Determine the order in which to perform tasks.", store=True
    )
    service_planned_stage = fields.Boolean(string="Enabled Planned Stage",
                                           config_parameter="industry_fsm.service_planned_stage",
                                           store=True)
    service_resolved_stage = fields.Boolean(string="Mark calls Done on Resolve",
                                            config_parameter="industry_fsm.service_resolved_stage", store=True)

    @api.model
    def set_values(self):
        super().set_values()
        config = self.env['ir.config_parameter'].sudo()

        config.set_param('industry_fsm.service_planned_stage', self.service_planned_stage)
        config.set_param('industry_fsm.service_resolved_stage', self.service_resolved_stage)

        # Update visibility (active status) of planning stage 2
        planned_stage = self.env.ref('industry_fsm.planning_project_stage_2', raise_if_not_found=False)
        fallback_stage = self.env.ref('industry_fsm.planning_project_stage_1', raise_if_not_found=False)

        if planned_stage:
            if not self.service_planned_stage:
                # Move all tasks from stage 2 to stage 1
                if fallback_stage:
                    tasks = self.env['project.task'].search([
                        ('stage_id', '=', planned_stage.id)
                    ])
                    tasks.write({'stage_id': fallback_stage.id})

            # Activate or deactivate the planned stage
            planned_stage.sudo().write({'active': self.service_planned_stage})

    @api.model
    def get_values(self):
        res = super().get_values()
        config = self.env['ir.config_parameter'].sudo()
        res.update({
            'service_planned_stage': config.get_param('industry_fsm.service_planned_stage', 'False') == 'True',
            'service_resolved_stage': config.get_param('industry_fsm.service_resolved_stage', 'False') == 'True',
        })
        return res

    @api.model
    def _get_basic_project_domain(self):
        return expression.AND([super()._get_basic_project_domain(), [('is_fsm', '=', False)]])

    @api.depends('group_industry_fsm_quotations')
    def _compute_module_industry_fsm_sale(self):
        for config in self:
            if config.group_industry_fsm_quotations:
                config.module_industry_fsm_sale = True

    @api.depends('module_industry_fsm_sale')
    def _compute_group_industry_fsm_quotations(self):
        for config in self:
            if not config.module_industry_fsm_sale:
                config.group_industry_fsm_quotations = False

    @api.onchange('service_planned_stage')
    def planned_stage_status(self):
        planned_stage_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'industry_fsm.service_planned_stage', 'False') == 'True'

        planned_stage = self.env.ref('industry_fsm.planning_project_stage_2', raise_if_not_found=False)

        if not planned_stage:
            return  # Stop execution if record is missing

        planned_stage.sudo().write({'active': planned_stage_enabled})