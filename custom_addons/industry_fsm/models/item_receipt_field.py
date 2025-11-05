from odoo import models, fields, api
from lxml import etree


class ItemReceiptField(models.Model):
    _name = 'item.receipt.field'
    _description = 'Item Receipt Field'

    name = fields.Char(string="Technical Name", required=True, readonly=True)
    field_label = fields.Char(string="Label", readonly=True)
    show_in_report = fields.Boolean(string="Show in Report", default=False)

    @api.model
    def populate_fields_from_service_call_form(self):
        # Store processed field names to later compare and clean up obsolete ones
        processed_fields = set()

        form_views = self.env['ir.ui.view'].search([
            ('model', '=', 'project.task'),
            ('type', '=', 'form'),
            '|', ('name', 'ilike', 'fsm'),
            ('arch_db', 'ilike', 'is_fsm')
        ])

        for form_view in form_views:
            try:
                xml = etree.fromstring(form_view.arch_db)
                field_nodes = xml.xpath('//field')
            except Exception:
                continue  # Skip any malformed views

            for node in field_nodes:
                field_name = node.get('name')
                if not field_name or field_name in processed_fields:
                    continue

                processed_fields.add(field_name)

                field = self.env['ir.model.fields'].search([
                    ('model', '=', 'project.task'),
                    ('name', '=', field_name)
                ], limit=1)

                if field:
                    # Check if it already exists
                    existing = self.search([('name', '=', field.name)], limit=1)
                    if not existing:
                        self.create({
                            'name': field.name,
                            'field_label': field.field_description,
                            'show_in_report': False
                        })

        # Delete fields no longer in any form view
        all_existing_names = self.search([]).mapped('name')
        obsolete_names = set(all_existing_names) - processed_fields
        if obsolete_names:
            self.search([('name', 'in', list(obsolete_names))]).unlink()

        return True

    @api.model
    def action_refresh_fields(self):
        self.populate_fields_from_service_call_form()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
