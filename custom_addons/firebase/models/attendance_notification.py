from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    devicetype = fields.Selection([
        ('web', 'Web'),
        ('android', 'Android'),
        ('ios', 'Ios')
    ], string="Device Type", default="web", tracking=False)  # Default to web if not provided

    @api.model
    def create(self, vals_list):
        """Override creates to send notification on check-in only if source is web."""
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
        attendances = super().create(vals_list)
        for attendance in attendances:
            try:
                # Send notification only if the check-in source is 'web'
                if attendance.check_in and attendance.devicetype == 'web':
                    user = attendance.employee_id.user_id
                    manager = attendance.employee_id.parent_id.user_id
                    if not user:
                        continue

                    check_in_time = attendance.check_in.strftime("%I:%M %p")
                    payload = {
                        'model': 'hr.attendance',
                        'record_id': str(attendance.id),
                        'check_in_time': check_in_time,
                        'employee_name': attendance.employee_id.name,
                        "silent": "true",
                        'action': "update_dayout"
                    }

                    # Send notification
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=[user.id],  # Needs to be a list of ids
                        title=None,
                        body=None,
                        payload=payload,
                    )
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=[manager.id],  # Needs to be a list of ids
                        title=None,
                        body=None,
                        payload=payload,
                    )

            except Exception as e:
                _logger.error(f"Failed to send check-in notification: {str(e)}")
                continue  # Continue processing other records even if one fails

        return attendances

    class HrAttendance(models.Model):
        _inherit = 'hr.attendance'

        def write(self, vals):
            """Override write to send notification on check-out"""
            # Store pre-write state of records
            pre_write_records = {rec.id: {'check_out': rec.check_out} for rec in self}

            result = super().write(vals)

            # Only process if check_out is being updated
            if 'check_out' in vals:
                for attendance in self:
                    try:
                        # Verify this is a new check-out (wasn't set before)
                        if attendance.check_out and not pre_write_records[attendance.id]['check_out']:
                            user = attendance.employee_id.user_id
                            manager = attendance.employee_id.parent_id.user_id
                            if not user:
                                continue

                            check_out_time = attendance.check_out.strftime("%I:%M %p")
                            # Calculate duration

                            payload = {
                                'model': 'hr.attendance',
                                'record_id': str(attendance.id),
                                'check_out_time': check_out_time,
                                'employee_name': attendance.employee_id.name,
                                "silent": "true",
                                'action': "update_dayout"
                            }

                            # Send notification
                            self.env['mobile.notification.service'].send_fcm_notification(
                                user_ids=[user.id, manager.id],  # Needs to be a list of ids
                                title=None,
                                body=None,
                                payload=payload,
                            )

                    except Exception as e:
                        _logger.error(f"Failed to send check-out notification: {str(e)}")
                        # Continue processing other records even if one fails
                        continue

            return result
