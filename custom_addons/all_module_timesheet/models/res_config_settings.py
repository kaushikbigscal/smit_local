from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_timesheet_entry = fields.Boolean(string="Auto Timesheet Entry",
                                          config_parameter="all_module_timesheet.auto_timesheet_entry",
                                          store=True)

    minimum_timesheet_duration = fields.Float(string="Minimum Timesheet Duration (minutes)")

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
