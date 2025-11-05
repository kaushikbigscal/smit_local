from datetime import datetime

import pytz
from odoo import models, fields, api, _


class IrModelFieldsMobile(models.Model):
    _name = 'ir.model.fields.mobile'
    _description = 'Mobile Fields for Models'

    field_id = fields.Many2one('ir.model.fields', string='Field', ondelete='set null', readonly=True)
    for_mobile = fields.Boolean(string="For Mobile", default=False)
    model_id = fields.Many2one('ir.model', string="Model", related='field_id.model_id', readonly=True)
    is_instant = fields.Boolean(string="Is Instant")
    is_caching = fields.Boolean(string="Enable Caching")
    caching_refresh_time = fields.Char(string="Caching Refresh Time", help="Enter time in HH:MM format")

    @api.onchange('is_caching')
    def reset_caching_refresh_time(self):
        if not self.is_caching:
            self.caching_refresh_time = False

    @api.model
    def action_create_fields(self):
        # Fetch all existing field IDs in ir.model.fields.mobile
        existing_field_ids = self.search([]).mapped('field_id.id')

        # Fetch all fields from 'ir.model.fields' that are not already in ir.model.fields.mobile
        fields_to_create = self.env['ir.model.fields'].search([('id', 'not in', existing_field_ids)])

        # Create records in 'ir.model.fields.mobile' only for non-duplicate fields
        for field in fields_to_create:
            self.create({
                'field_id': field.id,
                'for_mobile': False,  # Default value
            })

        # Remove fields from ir.model.fields.mobile that no longer exist in ir.model.fields
        fields_to_remove = self.search([('field_id', 'not in', self.env['ir.model.fields'].search([]).ids)])
        fields_to_remove.unlink()  # Delete the records

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    # def action_create_fields(self):
    #     # Fetch all existing field IDs in ir.model.fields.mobile
    #     existing_field_ids = self.search([]).mapped('field_id.id')
    #
    #     # Fetch all fields from 'ir.model.fields' that are not already in ir.model.fields.mobile
    #     fields_to_create = self.env['ir.model.fields'].search([('id', 'not in', existing_field_ids)])
    #
    #     # Create records in 'ir.model.fields.mobile' only for non-duplicate fields
    #     for field in fields_to_create:
    #         self.create({
    #             'field_id': field.id,
    #             'for_mobile': False,  # Default value
    #         })
    #
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'reload',
    #     }
