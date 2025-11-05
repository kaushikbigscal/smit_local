# from odoo import models, fields, api
#
#
# class IrModelFieldsMobile(models.Model):
#     _name = 'ir.model.fields.mobile'
#     _description = 'Mobile Fields for Models'
#
#     field_id = fields.Many2one('ir.model.fields', string='Field', ondelete='set null', readonly=True)
#     for_mobile = fields.Boolean(string="For Mobile", default=False)
#     model_id = fields.Many2one('ir.model', string="Model", related='field_id.model_id', readonly=True)
#
#     def action_create_fields(self):
#         # Fetch all existing field IDs in ir.model.fields.mobile
#         existing_field_ids = self.search([]).mapped('field_id.id')
#
#         # Fetch all fields from 'ir.model.fields' that are not already in ir.model.fields.mobile
#         fields_to_create = self.env['ir.model.fields'].search([('id', 'not in', existing_field_ids)])
#
#         # Create records in 'ir.model.fields.mobile' only for non-duplicate fields
#         for field in fields_to_create:
#             self.create({
#                 'field_id': field.id,
#                 'for_mobile': False,  # Default value
#             })
#
#         return {
#             'type': 'ir.actions.client',
#             'tag': 'reload',
#         }
#
#     # def get_field_for_mobile(self, model_name, field_name):
#     #     """
#     #     Retrieve the 'for_mobile' value for a specific model and field name.
#     #     :param model_name: The name of the model (e.g., 'res.partner')
#     #     :param field_name: The name of the field (e.g., 'name')
#     #     :return: Boolean value of 'for_mobile'.
#     #     """
#     #     # Search for the mobile field record using the model and field name
#     #     field_record = self.env['ir.model.fields'].search([('model', '=', model_name), ('name', '=', field_name)],
#     #                                                       limit=1)
#     #
#     #     # Find the corresponding 'ir.model.fields.mobile' record and return its 'for_mobile' value
#     #     if field_record:
#     #         mobile_field = self.env['ir.model.fields.mobile'].search([('field_id', '=', field_record.id)], limit=1)
#     #         return mobile_field.for_mobile if mobile_field else False
#     #     return False
