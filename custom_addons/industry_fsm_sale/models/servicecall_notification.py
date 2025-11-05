from odoo import models, api, _
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ServiceCall(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        """Send notification and chatter message when a new FSM task is assigned."""
        tasks = super().create(vals_list)

        for task in tasks:
            if task.is_fsm:

                # message_notify: In-App/Email Notification
                subject = _("You have been assigned to call %s", task.display_name)
                model_description = self.env['ir.model']._get(self._name).display_name
                customer_name = task.partner_id.name or "Unknown Customer"
                ticket_id = task.sequence_fsm or "Unknown Ticket ID"
                product_name = task.customer_product_id.product_id.name or "Unknown Product"

                for user in task.user_ids:
                    assignee_name = user.sudo().name
                    body_html = _(
                        "Hello %s,"
                        f"New Call {ticket_id} assigned to you for Customer {customer_name}, {product_name}"
                    ) % (assignee_name)

                    task.message_notify(
                        partner_ids=[user.partner_id.id],
                        subject=subject,
                        body=body_html,
                        record_name=task.display_name,
                        email_layout_xmlid='mail.mail_notification_layout',
                        model_description=model_description,
                        mail_auto_delete=False,
                    )

        return tasks


    def write(self, vals):
        _logger.info("Write called on project.task with vals: %s", vals)

        # Skip notification if this is an automatic stage change from industry_fsm
        if self.env.context.get('skip_notification'):
            _logger.info("Skipping notification due to context 'skip_notification'")
            return super().write(vals)

        old_is_fsm = {task.id: task.is_fsm for task in self}
        old_stages = {task.id: task.stage_id.id for task in self}
        old_users = {task.id: task.user_ids for task in self}

        service_resolved_stage = self.env['ir.config_parameter'].sudo().get_param(
            'industry_fsm.service_resolved_stage', default='False') == 'True'

        _logger.info("Service resolved stage config: %s", service_resolved_stage)

        resolved_stage = self.env['project.task.type'].search([('name', '=', 'Resolved')], limit=1)
        done_stage = self.env['project.task.type'].search([('name', '=', 'Done')], limit=1)
        resolved_stage_id = resolved_stage.id if resolved_stage else None
        done_stage_id = done_stage.id if done_stage else None

        _logger.info("Resolved Stage ID: %s, Done Stage ID: %s", resolved_stage_id, done_stage_id)

        tasks_will_auto_resolve = []
        if (service_resolved_stage and 'stage_id' in vals and
                vals['stage_id'] == resolved_stage_id and resolved_stage_id and done_stage_id):
            for task in self:
                if task.is_fsm and task.stage_id.id != resolved_stage_id:
                    tasks_will_auto_resolve.append(task.id)
            _logger.info("Tasks that will auto-resolve: %s", tasks_will_auto_resolve)

        res = super().write(vals)
        model_description = self.env['ir.model']._get(self._name).display_name

        for task in self:
            is_fsm = old_is_fsm.get(task.id) or task.is_fsm
            if is_fsm and resolved_stage_id and done_stage_id:
                old_stage = old_stages.get(task.id)
                new_stage = task.stage_id.id
                should_send_stage = False

                if not service_resolved_stage:
                    if old_stage != resolved_stage_id and new_stage == resolved_stage_id:
                        should_send_stage = True
                else:
                    if task.id in tasks_will_auto_resolve:
                        should_send_stage = True
                    elif old_stage != done_stage_id and new_stage == done_stage_id and old_stage == resolved_stage_id:
                        should_send_stage = True

                _logger.info("Task %s stage change: old=%s, new=%s, notify=%s",
                              task.id, old_stage, new_stage, should_send_stage)

                if should_send_stage:
                    ticket_id = task.sequence_fsm or "Unknown Ticket ID"
                    customer_name = task.partner_id.name or "Unknown Customer"
                    engineer_name = ", ".join(task.user_ids.mapped('name')) or "Unknown Engineer"
                    creator = task.create_uid

                    _logger.info("Sending notification for task %s (Ticket %s): Resolved by %s",
                                 task.id, ticket_id, engineer_name)

                    body_html = Markup(
                        f"{ticket_id} has been resolved by {engineer_name} for Customer {customer_name}"
                    )

                    task.message_notify(
                        partner_ids=[creator.partner_id.id],
                        subject=_("Task Resolved: %s", task.display_name),
                        body=body_html,
                        record_name=task.display_name,
                        email_layout_xmlid='mail.mail_notification_layout',
                        model_description=model_description,
                        mail_auto_delete=False,
                    )

            # --- Assigned User Notification ---
            if is_fsm:
                old_u = old_users.get(task.id, self.env['res.users'])
                new_u = task.user_ids
                added_users = (new_u - old_u)

                if added_users:
                    customer_name = task.partner_id.name or "Unknown Customer"
                    product_name = task.customer_product_id.product_id.name or "Unknown Product"
                    ticket_id = task.sequence_fsm or "Unknown Ticket ID"

                    for user in added_users:
                        partner_id = user.partner_id.id
                        subject = _("You have been assigned to call %s", task.display_name)
                        body_html = Markup(
                            "Hello %s,"
                            f" New Call {ticket_id} assigned to you for Customer {customer_name}, {product_name}"
                        ) % (user.sudo().name)

                        task.message_notify(
                            partner_ids=[partner_id],
                            subject=subject,
                            body=body_html,
                            record_name=task.display_name,
                            email_layout_xmlid='mail.mail_notification_layout',
                            model_description=model_description,
                            mail_auto_delete=False,
                        )

                        _logger.info(
                            "message_notify sent:\n"
                            "  To Partner ID(s): %s\n"
                            "  Subject: %s\n"
                            "  Body: %s\n"
                            "  Record Name: %s\n"
                            "  Model Description: %s\n"
                            "  Ticket ID: %s\n"
                            "  User ID: %s (Name: %s)",
                            [partner_id],
                            subject,
                            body_html,
                            task.display_name,
                            model_description,
                            ticket_id,
                            user.id,
                            user.name
                        )

        return res