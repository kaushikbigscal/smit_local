from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    max_late_check_ins = fields.Integer(
        string='Max Late Day-ins',
        default=3,
        help='Maximum number of late day-ins allowed before a leave is created.'
    )
    max_early_check_outs = fields.Integer(
        string='Max Early Day-outs',
        default=3,
        help='Maximum number of early day-outs allowed before a leave is created.'
    )

    minute_allowed = fields.Integer(
        string="Minute Allowed",
        default=15,
        help='Grace time allowed after the working start time before the late day-in counter increases.'
    )

    leave_type_id = fields.Many2one(
        'hr.leave.type',
        string="Leave Type",
        help="Select the type of leave",
        required=True,
    )
    notification_late_day_in = fields.Boolean(string="Notification For Late Day in", default=False)


    @api.model
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('hr_attendance.max_late_check_ins', self.max_late_check_ins)
        self.env['ir.config_parameter'].set_param('hr_attendance.max_early_check_outs', self.max_early_check_outs)
        self.env['ir.config_parameter'].set_param('hr_attendance.minute_allowed', self.minute_allowed)
        self.env['ir.config_parameter'].set_param('hr_attendance.notification_late_day_in',self.notification_late_day_in)
        # self.env['ir.config_parameter'].set_param('hr_attendance.leave_type_id',self.leave_type_id.id)
        if self.leave_type_id:
            self.env['ir.config_parameter'].set_param('hr_attendance.leave_type_id', self.leave_type_id.id)
        else:
            self.env['ir.config_parameter'].set_param('hr_attendance.leave_type_id', False)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'notification_late_day_in' : bool(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.notification_late_day_in',default=False)),
            'max_late_check_ins': int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.max_late_check_ins', default=3)),
            'max_early_check_outs': int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.max_early_check_outs', default=3)),
            'minute_allowed': int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=15)),
            # 'leave_type_id': self.env['ir.config_parameter'].sudo().get_param('hr_attendance.leave_type_id')
            'leave_type_id': int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.leave_type_id', default=False)) or False
        })

        return res
