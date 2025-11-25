from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    # user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    device_token = fields.Char(string='Device Token')
    last_used = fields.Datetime(string='Last Used')

    _sql_constraints = [
        ('unique_user_device_token', 'unique(device_token)', 'Device token must be unique per user')
    ]

    def write(self, vals):
        allowed_fields = ['device_token', 'last_used']

        # If user is NOT an Administrator
        if not self.env.user.has_group('base.group_system'):
            # If user is Portal or Internal
            if self.env.user.has_group('base.group_portal') or self.env.user.has_group('base.group_user'):
                for field in vals.keys():
                    if field not in allowed_fields:
                        pass
                        # raise AccessError(
                        #     "You are only allowed to update the fields: device_token and last_used."
                        # )
        return super(ResUsers, self).write(vals)

    @api.model
    def register_device_token(self, user_id, device_token, platform):
        """
        Register or update device token for a user
        """
        try:
            existing_token = self.search([
                ('id', '=', user_id),
                ('device_token', '=', device_token)
            ])

            if existing_token:
                existing_token.write({
                    'last_used': fields.Datetime.now(),
                    'active': True
                })
                return existing_token.id

            return self.create({
                'user_id': user_id,
                'device_token': device_token,
                'platform': platform,
                'last_used': fields.Datetime.now()
            }).id

        except Exception as e:
            self.env['notification.log'].create_log(
                'device_token_registration',
                f'Error registering device token: {str(e)}'
            )
            return False


from odoo import models, fields, api, _


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def write(self, vals):
        res = super(HrLeave, self).write(vals)

        # Check if state is being changed
        if 'state' in vals and vals['state'] == 'validate1':
            for leave in self:
                leave.message_notify(
                    body=_('Your %(leave_type)s planned on %(date)s has been approved first approval',
                           leave_type=leave.holiday_status_id.display_name, date=leave.date_from),
                    partner_ids=[leave.employee_id.user_id.partner_id.id] if leave.employee_id.user_id else [],
                )
        return res


import logging

_logger = logging.getLogger(__name__)  # Initialize logger


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def action_feedback(self, **kwargs):
        _logger.info(">> action_feedback triggered with kwargs: %s", kwargs)

        for activity in self:
            _logger.info(">> Processing activity ID: %s", activity.id)
            _logger.info("   - Summary: %s", activity.summary)
            _logger.info("   - Assigned to: %s", activity.user_id.name)
            _logger.info("   - Created by: %s", activity.create_uid.name)
            _logger.info("   - Model: %s, Res ID: %s", activity.res_model, activity.res_id)

            # Only notify if someone else created the activity
            if activity.create_uid and activity.create_uid != self.env.user:
                try:
                    if activity.res_model and activity.res_id:
                        record = self.env[activity.res_model].browse(activity.res_id)
                        _logger.info(">> Sending message_notify to creator: %s", activity.create_uid.partner_id.name)

                        record.message_notify(
                            subject="Activity Marked as Done",
                            body=f"Activity {activity.summary or activity.activity_type_id.name} assigned to {activity.user_id.name} was marked as Done.",
                            partner_ids=[activity.create_uid.partner_id.id],
                        )
                except Exception as e:
                    _logger.error("!! Failed to send notification for activity %s: %s", activity.id, str(e))
            else:
                _logger.info(">> Skipping notification: activity created by same user")

        return super().action_feedback(**kwargs)

    def unlink(self):
        for activity in self:
            _logger.info(">> Deleting activity ID: %s", activity.id)
            _logger.info("   - Summary: %s", activity.summary)
            _logger.info("   - Assigned to: %s", activity.user_id.name)
            _logger.info("   - Created by: %s", activity.create_uid.name)
            _logger.info("   - Model: %s, Res ID: %s", activity.res_model, activity.res_id)

            if activity.create_uid and activity.create_uid != self.env.user:
                try:
                    record = self.env[activity.res_model].browse(activity.res_id)
                    record.message_notify(
                        subject="Activity Cancelled",
                        body=f"The activity {activity.summary or activity.activity_type_id.name} assigned to {activity.user_id.name} was Cancelled.",
                        partner_ids=[activity.create_uid.partner_id.id],
                    )
                    _logger.info(">> Notification sent to creator.")
                except Exception as e:
                    _logger.error("!! Failed to notify on cancel: %s", str(e))
        return super().unlink()
