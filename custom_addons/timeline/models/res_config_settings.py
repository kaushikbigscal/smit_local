# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Employee Timeline Configuration
    employee_timeline_model_ids = fields.Many2many(
        "ir.model",
        "res_config_employee_timeline_model_rel",
        "config_id",
        "model_id",
        string="Employee Timeline Models",
        help="Select models to scan for employee-linked records. Only models with many2one fields to hr.employee or res.users will be effective.",
        domain=[('transient', '=', False)]
    )

    # Customer Timeline Configuration
    customer_timeline_model_ids = fields.Many2many(
        "ir.model",
        "res_config_customer_timeline_model_rel",
        "config_id",
        "model_id",
        string="Customer Timeline Models",
        help="Select models to scan for customer-linked records. Only models with many2one fields to res.partner will be effective.",
        domain=[('transient', '=', False)]
    )

    def set_values(self):
        super().set_values()
        params = self.env["ir.config_parameter"].sudo()

        employee_ids = self.employee_timeline_model_ids.exists().ids
        customer_ids = self.customer_timeline_model_ids.exists().ids

        params.set_param("timeline.employee_timeline_model_ids", json.dumps(employee_ids))
        params.set_param("timeline.customer_timeline_model_ids", json.dumps(customer_ids))

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()

        # Get configuration parameters
        employee_model_ids_str = params.get_param("timeline.employee_timeline_model_ids", "[]")
        customer_model_ids_str = params.get_param("timeline.customer_timeline_model_ids", "[]")

        try:
            employee_model_ids = json.loads(employee_model_ids_str) if employee_model_ids_str else []
        except Exception:
            employee_model_ids = []

        try:
            customer_model_ids = json.loads(customer_model_ids_str) if customer_model_ids_str else []
        except Exception:
            customer_model_ids = []

        # Filter out deleted models
        employee_model_ids = self.env["ir.model"].browse(employee_model_ids).exists().ids
        customer_model_ids = self.env["ir.model"].browse(customer_model_ids).exists().ids

        res.update({
            'employee_timeline_model_ids': [(6, 0, employee_model_ids)],
            'customer_timeline_model_ids': [(6, 0, customer_model_ids)],
        })
        return res
