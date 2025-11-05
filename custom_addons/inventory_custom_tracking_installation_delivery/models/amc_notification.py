from odoo import models,fields,api

class AmcNotification(models.Model):
    _inherit = 'amc.contract'

    @api.model
    def create(self, vals_list):
        """Send notification when a new task is assigned (only if is_fsm is False)."""
        contracts = super().create(vals_list)

        for contract in contracts:
            assigned_users = contract.user_ids.filtered(lambda user: user.device_token)
            if assigned_users:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=assigned_users.ids,
                    title="Create AMC Contract",
                    body="New AMC contract created and assigned to you",
                    payload={
                        'model': 'amc.contract',
                        'record_id': str(contract.id),
                        'action': 'new_amc_contract_created',
                        'silent': 'true'
                    }
                )
                print("Successfully send notification")
            users=contract.user_ids
            if users:
                partner_ids = users.mapped('partner_id.id')
                contract.message_notify(
                    partner_ids=partner_ids,
                    subject="New AMC Contract Assigned",
                    body="You have been assigned a new AMC Contract: %s" % contract.name,
                    subtype_xmlid='mail.mt_note',
                    email_layout_xmlid='mail.mail_notification_light'
                )
                print("Web push of AMC Contract")
        return contracts


    def write(self, vals):
        """Send notifications when users are assigned or unassigned from tasks (only if is_fsm is False)."""
        contracts = self
        old_users = {contract.id: contract.user_ids for contract in contracts}

        res = super(AmcNotification, self).write(vals)

        for contract in contracts:
            old_u = old_users.get(contract.id, self.env['res.users'])
            new_u = contract.user_ids
            removed_user = (old_u - new_u)
            removed_users = (old_u - new_u).filtered(lambda user: user.device_token)
            added_user = (new_u - old_u)
            added_users = (new_u - old_u).filtered(lambda user: user.device_token)

            if removed_users:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=removed_users.ids,
                    title="Contract assigned",
                    body="AMC Contract unassigned to you",
                    payload={
                        'model': 'amc.contract',
                        'record_id': str(contract.id),
                        'action': 'amc_contract_unassigned',
                        'silent': 'true'
                    }
                )
                print("amc contract unassigned")

            if removed_user:
                partner_ids = removed_user.mapped('partner_id.id')
                contract.message_notify(
                    partner_ids=partner_ids,
                    subject="AMC Contract Unassigned",
                    body="You have been unassigned a AMC Contract: %s" % contract.name,
                    subtype_xmlid='mail.mt_note',
                    email_layout_xmlid='mail.mail_notification_light'
                )
                print("WEB Push for unassigned")

            if added_users:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=added_users.ids,
                    title="AMC Contract assigned",
                    body="AMC Contract assigned to you",
                    payload={
                        'model': 'amc.contract',
                        'record_id': str(contract.id),
                        'action': 'amc_contract_assigned',
                        'silent': 'true'
                    }
                )
                print("amc_contract_assigned")

            if added_user:
                partner_ids = added_user.mapped('partner_id.id')
                contract.message_notify(
                    partner_ids=partner_ids,
                    subject="AMC Contract assigned",
                    body="You have been assigned a AMC Contract: %s" % contract.name,
                    subtype_xmlid='mail.mt_note',
                    email_layout_xmlid='mail.mail_notification_light'
                )
                print("WEB Push for assigned")

        return res

    def unlink(self):
        """Send notification before a task is deleted (only if is_fsm is False)."""
        contracts = self
        users_to_notify = contracts.mapped('user_ids').filtered(lambda user: user.device_token)
        user=contracts.mapped('user_ids')
        if users_to_notify:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=users_to_notify.ids,
                title=None,
                body=None,
                payload={
                    'model': 'amc.contract',
                    'record_id': ','.join(map(str, contracts.ids)),
                    'action': 'amc_contract_deletion',
                    'silent': 'true'
                }
            )
            print("AMC Contract deleted")


        if user:
            partner_ids = user.mapped('partner_id.id')
            contracts.message_notify(
                partner_ids=partner_ids,
                subject="AMC Contract deleted",
                body="AMC Contract: %s deleted" % contracts.name,
                subtype_xmlid='mail.mt_note',
                email_layout_xmlid='mail.mail_notification_light'
            )
            print("WEB Push for deleted")

        return super(AmcNotification, self).unlink()



class VisitNotification(models.Model):
    _inherit = 'amc.contract.visit'


    @api.model
    def create(self, vals_list):
        """Send notification when a new task is assigned (only if is_fsm is False)."""
        visit = super().create(vals_list)

        for visits in visit:
            assigned_users = visits.technician_ids.filtered(lambda user: user.device_token)
            if assigned_users:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=assigned_users.ids,
                    title="Create AMC Contract",
                    body="New AMC contract created and assigned to you",
                    payload={
                        'model': 'amc.contract.visit',
                        'record_id': str(visits.id),
                        'action': 'new_visit_created',
                        'silent': 'true'
                    }
                )
                print("Successfully send notification")
            users=visits.technician_ids
            if users:
                partner_ids = users.mapped('partner_id.id')
                visit.message_notify(
                    partner_ids=partner_ids,
                    subject="New AMC Schedule visit created",
                    body="You have been assigned a schedule visit of AMC Contract: %s",
                    subtype_xmlid='mail.mt_note',
                    email_layout_xmlid='mail.mail_notification_light'
                )
                print("Web push of AMC Contract")
        return visit


