# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    send_payslip_by_email = fields.Boolean(string="Automatic Send Payslip By Mail", default=True)
    mandatory_bank_details = fields.Boolean(string="Mandatory Bank Details")
    mandatory_identity_details = fields.Boolean(string="Mandatory Identity Details")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        send_payslip_by_email = params.get_param('send_payslip_by_email', default=True)
        mandatory_bank_details = params.get_param('hr_payroll.mandatory_bank_details')
        mandatory_identity_details = params.get_param('hr_payroll.mandatory_identity_details')
        res.update(
            send_payslip_by_email=send_payslip_by_email,
            mandatory_bank_details=mandatory_bank_details,
            mandatory_identity_details=mandatory_identity_details

        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param("send_payslip_by_email",
                                                         self.send_payslip_by_email)
        self.env['ir.config_parameter'].sudo().set_param("hr_payroll.mandatory_bank_details",
                                                         self.mandatory_bank_details)
        self.env['ir.config_parameter'].sudo().set_param("hr_payroll.mandatory_identity_details",
                                                         self.mandatory_identity_details)
