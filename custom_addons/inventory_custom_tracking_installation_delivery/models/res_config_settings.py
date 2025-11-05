from odoo import models,fields,api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    amc_new_estimation = fields.Boolean(
        string=" Create New Estimation ",
        config_parameter="inventory_custom_tracking_installation_delivery.amc_new_estimation"
    )

    days_before_schedule_visit = fields.Integer(
        string="Days Before Schedule Visit",
        default=0,
        config_parameter='inventory_custom_tracking_installation_delivery.days_before_schedule_visit',
        help="Number of days before the scheduled visit to create the service call"
    )

    amc_contract_reminder_days = fields.Integer(
        string="AMC Contract Days Limit",
        config_parameter='reminder.amc_days_limit'
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res.update({
            'days_before_schedule_visit': int(self.env['ir.config_parameter'].sudo().get_param(
                'inventory_custom_tracking_installation_delivery.days_before_schedule_visit', default=0)),
        })
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'inventory_custom_tracking_installation_delivery.days_before_schedule_visit',
            self.days_before_schedule_visit
        )
