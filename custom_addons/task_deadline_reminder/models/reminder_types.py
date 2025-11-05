from odoo import models, fields, _
from odoo.exceptions import UserError


class ReminderTypes(models.Model):
    _name = 'reminder.types'
    _description = 'Reminder types'

    name = fields.Char(string="Reminder Types")
    reminder_minutes = fields.Integer(string="Reminder Offset (in minutes)")

    def unlink(self):
        # Define the default/protected reminder types that cannot be deleted
        protected_types = ['10 Minutes Before', '1 Hour Before', '1 Day Before', 'Custom']

        for rec in self:
            # Check if this is a protected/default reminder type
            if rec.name in protected_types:
                raise UserError(
                    _("Default reminder type '%s' cannot be deleted as it is a system default.") % rec.name
                )

            # For non-protected types, check if they are being used
            used_in_tasks = self.env['project.task'].search_count([('reminder_type_ids', 'in', rec.id)])
            used_in_activities = self.env['mail.activity'].search_count([('reminder_type_ids', 'in', rec.id)])

            if used_in_tasks or used_in_activities:
                raise UserError(
                    _("Reminder type '%s' is being used in tasks or activities and cannot be deleted.") % rec.name
                )

        return super(ReminderTypes, self).unlink()

    def write(self, vals):
        protected_types = ['10 Minutes Before', '1 Hour Before', '1 Day Before', 'Custom']

        for rec in self:
            if rec.name in protected_types:
                raise UserError(
                    _("You cannot modify the default reminder type '%s'. Changes are not allowed.") % rec.name
                )
        return super(ReminderTypes, self).write(vals)
