# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
#
#
# class ValidateTaskWizard(models.TransientModel):
#     _name = 'validate.task.wizard'
#     _description = 'Validate Task Wizard'
#
#     installation_task_checkbox = fields.Boolean(string="Installation Task")
#     assignee_id = fields.Many2many('res.users', string="Assignees")
#
#     def action_save_and_close(self):
#         if self.installation_task_checkbox == True:
#             try:
#                 user_ids = self.assignee_id.ids
#                 # Create project and task if checkbox is True
#                 task = self.env['project.task'].create({
#                     'name': 'Installation Task',
#                     'user_ids': [(6, 0, user_ids)],
#                 })
#                 # Check if current user is not in the user_ids list
#                 if self.env.user.id not in user_ids:
#                     # Remove the current user from the user_ids
#                     task.write({
#                         'user_ids': [(3, self.env.user.id)]
#                     })
#
#             except ValueError as e:
#                 raise ValidationError(_("Error creating task or validating delivery order: %s") % e)
#
#         # Validate the delivery regardless of the checkbox state
#         # picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
#         # picking.button_validate()
#         # picking.write({'state': 'done'})
#
#         return {'type': 'ir.actions.act_window_close'}

from odoo import models, fields, _
from odoo.exceptions import ValidationError


class ValidateTaskWizard(models.TransientModel):
    _name = 'validate.task.wizard'
    _description = 'Validate Task Wizard'

    installation_task_checkbox = fields.Boolean(string="Installation Task")
    assignee_id = fields.Many2many('res.users', string="Assignees")

    def action_save_and_close(self):
        if self.installation_task_checkbox:
            try:
                user_ids = self.assignee_id.ids

                # Fetch the stock.picking record
                picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
                if not picking:
                    raise ValidationError(_("No delivery order found."))

                partner = picking.partner_id
                installation_date = picking.installation_date

                if not partner:
                    raise ValidationError(_("No partner is associated with the delivery order."))

                # Format the installation date
                installation_date_str = fields.Date.to_string(
                    installation_date) if installation_date else "Installation date not set"

                # Partner details
                partner_name = partner.name
                address_parts = [partner.street, partner.city, partner.state_id.name, partner.zip,
                                 partner.country_id.name]
                full_address = ", ".join(filter(None, address_parts)) or "No address available"
                mobile = partner.mobile or "Not available"
                phone = partner.phone or "Not available"
                contact_number = mobile if mobile != "Not available" else phone

                task_name = f"Installation Task - {partner_name[:30]} - {contact_number[:30]}"

                description = f"""
                    Installation Date: {installation_date_str}<br/>
                    Customer's Full Address: {full_address}<br/>
                    Mobile: {mobile}<br/>
                    Phone: {phone}<br/>
                    Delivery Number: {picking.name}
                """

                task = self.env['project.task'].create({
                    'name': task_name,
                    'user_ids': [(6, 0, user_ids)],
                    'description': description,
                })
                # Remove the current user from the user_ids if not included
                if self.env.user.id not in user_ids:
                    task.write({
                        'user_ids': [(3, self.env.user.id)],
                    })

            except ValidationError as e:
                raise e
            except Exception as e:
                raise ValidationError(_("Unexpected error occurred: %s") % str(e))

        return {'type': 'ir.actions.act_window_close'}
