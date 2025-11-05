from odoo import fields, models, api

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        company_ids = res.mapped('company_id.id')  # Get unique company IDs

        if company_ids:
            employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
            valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')
            payload = {
                'model': 'resource.calendar.leaves',
                'record_id': str(res[0].id),  # Use first record's ID for payload
                'action': 'holiday_added',
                'silent': 'true'
            }
            _logger.info("Payload (create): %s", payload)
            if valid_user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=valid_user_ids,
                    title="Notification of creation",
                    body="Public holiday is added in your company",
                    payload={
                        'model': 'resource.calendar.leaves',
                        'record_id': str(res[0].id),  # Use first record's ID for payload
                        'action': 'holiday_added',
                        'silent': 'true'
                    }
                )
                _logger.info("Payload (create): %s", payload)

            return res

        def write(self, vals):
            """Send notification when a public holiday is updated."""
            res = super().write(vals)

            company_ids = self.mapped('company_id.id')  # Get unique company IDs

            if company_ids:
                employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
                valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')
                payload = {
                    'model': 'resource.calendar.leaves',
                    'record_id': str(self[0].id),  # Use first record's ID for payload
                    'action': 'holiday_updated',
                    'silent': 'true'
                }
                _logger.info("Payload (write): %s", payload)

                if valid_user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=valid_user_ids,
                        title="Public Holiday Updated",
                        body="A public holiday has been updated in your company.",
                        payload={
                            'model': 'resource.calendar.leaves',
                            'record_id': str(self[0].id),  # Use first record's ID for payload
                            'action': 'holiday_updated',
                            'silent': 'true'
                        }
                    )

            return res

        def unlink(self):
            company_ids = self.mapped('company_id.id')  # Get unique company IDs

            if company_ids:
                employees = self.env['hr.employee'].search([('company_id', 'in', company_ids)])
                valid_user_ids = employees.mapped('user_id').filtered(lambda u: u.device_token).mapped('id')

                record_ids = self.mapped('id')  # Collect record IDs before deletion

                res = super().unlink()  # Delete records
                payload = {
                    'model': 'resource.calendar.leaves',
                    'record_id': str(record_ids[0]),  # Use first deleted record's ID
                    'action': 'holiday_deleted',
                    'silent': 'true'
                }
                _logger.info("Payload (unlink): %s", payload)

                if valid_user_ids and record_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=valid_user_ids,
                        title="Notification of deletion",
                        body="Public holiday is deleted successfully",
                        payload={
                            'model': 'resource.calendar.leaves',
                            'record_id': str(record_ids[0]),  # Use first deleted record's ID
                            'action': 'holiday_deleted',
                            'silent': 'true'
                        }
                    )

                return res

    class HrLeave(models.Model):
        _inherit = 'hr.leave'

        @api.model_create_multi
        def create(self, vals_list):
            # Create the leave record first
            if not isinstance(vals_list, list):
                vals_list = [vals_list]

                # Create leave records
            leaves = super().create(vals_list)

            # Process notifications
            for vals, leave in zip(vals_list, leaves):
                # Check if the leave applicant has a manager
                applicant = self.env['hr.employee'].browse(vals.get('employee_id'))

                # Find the manager/approver
                if applicant.parent_id and applicant.parent_id.user_id:
                    # Prepare notification payload
                    payload = {
                        'model': 'hr.leave',
                        'record_id': str(leave.id),
                        'action': 'view_leave_request'
                    }

                    # Send FCM notification to the manager
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=applicant.parent_id.user_id.id,
                        title='New Leave Request',
                        body=f'Leave request from {applicant.name} requires your approval',
                        payload=payload
                    )

            return leaves

        def write(self, vals):
            # Store the original state before update
            original_states = {
                record.id: {
                    'state': record.state,
                    'number_of_days': record.number_of_days
                } for record in self
            }
            print(original_states)

            # Perform the write operation

            for record in self:
                # Check for manager notification when employee_id changes
                if 'employee_id' in vals:
                    # Check if record has a manager
                    if record.employee_id.parent_id and record.employee_id.parent_id.user_id:
                        payload = {
                            'model': 'hr.leave',
                            'record_id': str(record.id),
                            'action': 'view_leave_request'
                        }

                        # Send notification to manager
                        self.env['mobile.notification.service'].send_fcm_notification(
                            user_ids=record.employee_id.parent_id.user_id.id,
                            title='Leave Request Update',
                            body=f'Leave request from {record.employee_id.name} has been updated',
                            payload=payload
                        )

                if 'number_of_days' in vals:
                    print("IN IF STATEMENT")
                    original_days = original_states[record.id]['number_of_days']
                    print(original_days)
                    new_days = record.number_of_days
                    print(new_days)
                    if original_days != new_days and record.employee_id.parent_id and record.employee_id.parent_id.user_id:
                        self.env['mobile.notification.service'].send_fcm_notification(
                            user_ids=record.employee_id.parent_id.user_id.id,
                            title='Leave Duration Updated',
                            body=f'Leave duration for {record.employee_id.name} has been changed to {new_days} day(s).',
                            payload={
                                'model': 'hr.leave',
                                'record_id': str(record.id),
                                'action': 'view_leave_request'
                            }
                        )

            res = super().write(vals)
            # Check for employee notification when state changes
            if 'state' in vals:
                for record in self:
                    # Check if state actually changed
                    if record.id in original_states:
                        # Prepare notification payload
                        payload = {
                            'model': 'hr.leave',
                            'record_id': str(record.id),
                            'action': 'view_leave_request'
                        }

                        # Determine a notification message based on new state
                        if record.state == 'validate':
                            title = 'Leave Approved'
                            body = f'Your leave request has been approved.'
                        elif record.state == 'refuse':
                            title = 'Leave Rejected'
                            body = f'Your leave request has been rejected.'
                        else:
                            # Skip if the state doesn't match approval/rejection
                            continue

                        # Ensure the employee has a user account
                        if record.employee_id.user_id:
                            # Send FCM notification to the employee
                            self.env['mobile.notification.service'].send_fcm_notification(
                                user_ids=record.employee_id.user_id.id,
                                title="Hello",
                                body=body,
                                payload=payload
                            )

            return res

    """Customer  Create/Delete"""
    from odoo import models, api

    class SaleTeam(models.Model):
        _inherit = 'res.partner'

        @api.model
        def create(self, vals_list):
            record = super(SaleTeam, self).create(vals_list)
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title="Customer Create",
                    body="New Customer is created in your company ",
                    payload={
                        'model': 'res.partner',
                        'record_id': str(record.id),
                        'action': 'customer_creation',
                        'silent': "true"
                    }
                )
            return record

        def write(self, vals):
            result = super(SaleTeam, self).write(vals)
            for record in self:
                # Skip notification if write_date == create_date (i.e., fresh after creation)
                if record.create_date and record.write_date and record.create_date == record.write_date:
                    continue

                users = self.env['res.users'].search([])
                user_ids = [user.id for user in users if user.device_token]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Customer update",
                        body="Customer Updated in your company",
                        payload={
                            'model': 'res.partner',
                            'record_id': str(record.id),
                            'action': 'customer_update',
                            'silent': "true"
                        }
                    )

            return result

        def unlink(self):
            for record in self:
                # Fetch all users with a registered device token
                users = self.env['res.users'].search([])
                user_ids = [user.id for user in users if user.device_token]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Customer exit",
                        body="Customer is deleted in your company",
                        payload={
                            'model': 'res.partner',
                            'record_id': str(record.id),
                            'action': 'customer_deletion',
                            'silent': "true"
                        }
                    )

            return super(SaleTeam, self).unlink()

    # ============= 24-04
    from idlelib.configdialog import changes
    # Service call setting changes
    from odoo import models

    class ResConfigSettings(models.TransientModel):
        _inherit = 'res.config.settings'

        def set_values(self):
            config = self.env['ir.config_parameter'].sudo()

            old_planned = config.get_param('industry_fsm.service_planned_stage', 'False') == 'True'
            old_resolved = config.get_param('industry_fsm.service_resolved_stage', 'False') == 'True'

            super(ResConfigSettings, self).set_values()

            new_planned = config.get_param('industry_fsm.service_planned_stage', 'False') == 'True'
            new_resolved = config.get_param('industry_fsm.service_resolved_stage', 'False') == 'True'

            if old_planned != new_planned or old_resolved != new_resolved:
                users = self.env['res.users'].search([('device_token', '!=', False)])
                user_ids = users.ids

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Service call",
                        body="Service call",
                        payload={
                            'model': 'res.config.settings',
                            'action': 'settings_update',
                            'silent': "true"
                        }
                    )

    # discuss model(channel,chat,update,pin,unpin)
    from odoo import models, api, tools

    class ChannelNotification(models.Model):
        _inherit = 'discuss.channel'

        @api.model
        def create(self, vals_list):
            record = super(ChannelNotification, self).create(vals_list)
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title="Channel Created",
                    body="Channel Created",
                    payload={
                        'model': 'discuss.channel',
                        'record_id': str(record.id),
                        'action': 'channel_creation',
                        'silent': "true"
                    }
                )
            return record

        def write(self, vals):
            result = super(ChannelNotification, self).write(vals)
            for record in self:
                # Skip notification if write_date == create_date (i.e., fresh after creation)
                if record.create_date and record.write_date and record.create_date == record.write_date:
                    continue

                users = self.env['res.users'].search([])
                user_ids = [user.id for user in users if user.device_token]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Channel updated",
                        body="Channel updated",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(record.id),
                            'action': 'channel_update',
                            'silent': "true"
                        }
                    )
            return result

        def unlink(self):
            for record in self:
                # Fetch all users with a registered device token
                users = self.env['res.users'].search([])
                user_ids = [user.id for user in users if user.device_token]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Channel deleted",
                        body="Channel deleted",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(record.id),
                            'action': 'channel_deletion',
                            'silent': "true"
                        }
                    )
            return super(ChannelNotification, self).unlink()

        def message_post(self, **kwargs):
            # Check for skip_notification context, including the pin action flag
            if self.env.context.get('skip_notification'):
                return super(ChannelNotification, self).message_post(**kwargs)

            message = super(ChannelNotification, self).message_post(**kwargs)
            current_user = self.env.user

            for channel in self:
                participants = channel.channel_partner_ids
                users = self.env['res.users'].search([
                    ('partner_id', 'in', participants.ids),
                    ('id', '!=', current_user.id),
                    ('device_token', '!=', False)
                ])

                user_ids = [user.id for user in users]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="New Message",
                        body="New Message",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(channel.id),
                            'action': 'message_sent',
                            'silent': "true"
                        }
                    )

            return message

        def set_message_pin(self, **kwargs):
            # Set the context flag to skip notifications in message_post
            context = dict(self.env.context, skip_notification=True)
            self = self.with_context(context)

            message = super(ChannelNotification, self).set_message_pin(**kwargs)

            current_user = self.env.user

            for channel in self:
                # Get channel participants
                participants = channel.channel_partner_ids

                # Get all users linked to those partners, excluding the sender
                users = self.env['res.users'].search([
                    ('partner_id', 'in', participants.ids),
                    ('id', '!=', current_user.id),
                    ('device_token', '!=', False)
                ])

                user_ids = [user.id for user in users]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Pin/Unpin Message",
                        body="Message is pin or unpin",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(channel.id),
                            'action': 'message_pin_unpin',
                            'silent': "true"
                        }
                    )

            return message

        def _message_update_content(self, message, body, attachment_ids=None, partner_ids=None,
                                    strict=True, **kwargs):

            result = super()._message_update_content(
                message, body, attachment_ids, partner_ids,
                strict=strict, **kwargs
            )

            if message.model == "discuss.channel" and message.res_id:
                channel = self.env["discuss.channel"].browse(message.res_id)
                current_user = self.env.user

                participants = channel.channel_partner_ids
                users = self.env['res.users'].search([
                    ('partner_id', 'in', participants.ids),
                    ('id', '!=', current_user.id),
                    ('device_token', '!=', False)
                ])

                user_ids = [user.id for user in users]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="Message Edited",
                        body=f"{current_user.name} edited a message in {channel.name}",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(channel.id),
                            'action': 'message_edited',
                            'silent': "true"
                        }
                    )

            return result

    # message reaction notification
    class MailMessage(models.Model):
        _inherit = 'mail.message'

        def _message_reaction(self, emoji, action):
            result = super()._message_reaction(emoji, action)

            if self.model == "discuss.channel" and self.res_id:
                channel = self.env["discuss.channel"].browse(self.res_id)
                current_user = self.env.user

                participants = channel.channel_partner_ids
                users = self.env['res.users'].search([
                    ('partner_id', 'in', participants.ids),
                    ('id', '!=', current_user.id),
                    ('device_token', '!=', False)
                ])

                user_ids = [user.id for user in users]

                if user_ids:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=user_ids,
                        title="New Reaction",
                        body=f"{current_user.name} reacted with {emoji} in {channel.name}",
                        payload={
                            'model': 'discuss.channel',
                            'record_id': str(channel.id),
                            'action': 'reaction_added_deleted',
                            'silent': "true"
                        }
                    )

            return result

    # inbox notification
    class MailThreadFCMInboxOnly(models.AbstractModel):
        _inherit = 'mail.thread'

        def _notify_thread(self, message, msg_vals=False, **kwargs):

            # Call the original _notify_thread to retain default behavior
            result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

            # Fetch inbox-type mail notifications related to this message
            inbox_notifications = self.env['mail.notification'].search([
                ('mail_message_id', '=', message.id),
                ('notification_type', '=', 'inbox'),
                ('res_partner_id.user_ids', '!=', False),
                ('res_partner_id.user_ids.device_token', '!=', False),
                ('is_read', '=', False)
            ])

            if not inbox_notifications:
                return result

            # Extract recipient users
            users_to_notify = inbox_notifications.mapped('res_partner_id.user_ids')
            users_to_notify = users_to_notify.filtered(lambda u: u.active and u.device_token)

            # Remove sender from recipient list
            author_user = message.author_id.user_ids[:1]
            users_to_notify = users_to_notify - author_user

            if not users_to_notify:
                return result

            # Build payload
            author_name = message.author_id.name
            fcm_payload = {
                'title': str(msg_vals.get('record_name') or f'New Message from {author_name}'),
                'body': str(tools.html2plaintext(message.body) or "Message"),
                'data': {
                    'message_id': str(message.id),
                    'model': str(message.model or ''),
                    'res_id': str(message.res_id or ''),
                    'record_name': str(message.record_name or ''),
                    'author_name': str(author_name),
                    'type': "inbox",
                    'silent': "true"

                }
            }

            device_tokens = [
                str(u.device_token).strip()
                for u in users_to_notify if u.device_token
            ]

            if device_tokens:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=users_to_notify.ids,
                    title=fcm_payload['title'],
                    body=fcm_payload['body'],
                    payload=fcm_payload['data']
                )

            return result
