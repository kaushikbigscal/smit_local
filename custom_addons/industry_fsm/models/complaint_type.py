from odoo import models, fields, api
from random import randint


class ComplaintType(models.Model):
    _name = 'complaint.type'
    _description = 'Complaint Type'
    _order = 'name'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(string='Color', default=_get_default_color)
    reason_code_ids = fields.One2many('reason.code', 'complaint_type_id', string='Reason Codes')

    show_in_portal = fields.Boolean(string="Show in Customer Portal")
    show_portal_field = fields.Boolean(compute='_compute_show_portal_field')

    def _compute_show_portal_field(self):
        module_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'customer_app'),
            ('state', '=', 'installed')
        ]) > 0
        for rec in self:
            rec.show_portal_field = module_installed

    attachment_on_out = fields.Boolean(string="Attachment Required on Check-out", default=True)
    report_id = fields.Many2one(
        'xml.upload',
        string='Report',
        domain="[('report_action', '=', 'action_xml_upload_custom_report_format_for_all_service_call')]"
    )
    resolved_required_fields = fields.Many2many(
        'ir.model.fields',
        string="Required Fields for Resolved Stage",
        domain=[('model', 'in', ['project.task', 'end.service.call.wizard'])],
        help="Select the fields that must be filled before moving to the 'Resolved' stage."
    )
    signed_required = fields.Boolean(string="signed required", default=True)

    # custom_fields_ids = fields.One2many('custom.fields', 'dynamic_fields_id', 'Custom Fields')
    custom_field = fields.Many2many(
        'dynamic.fields',
        string='Custom Fields',
        domain="[('model_id.model', '=', 'end.service.call.wizard')]"
    )

    @api.model
    def default_get(self, fields_list):
        res = super(ComplaintType, self).default_get(fields_list)

        if 'custom_fields_ids' in fields_list:
            dynamic_fields = self.env['dynamic.fields'].search([
                ('model_id.model', '=', 'end.service.call.wizard')
            ])
            custom_field_lines = []
            for field in dynamic_fields:
                custom_field_lines.append((0, 0, {
                    'custom_field': field.id
                }))
            res['custom_fields_ids'] = custom_field_lines

        return res


class ReasonCode(models.Model):
    _name = 'reason.code'
    _description = 'Reason Code'

    name = fields.Char(string='Reason Code', required=True)
    complaint_type_id = fields.Many2one('complaint.type', string='Complaint Type', ondelete='cascade')


# class CustomFields(models.Model):
#     _name = 'custom.fields'
#     _description = 'Custom Fields'
#
#     dynamic_fields_id = fields.Many2one('complaint.type', string='Dynamic Field Reference')
#     custom_field = fields.Many2one(
#         'dynamic.fields',
#         string='Custom Fields',
#         domain="[('model_id.model', '=', 'end.service.call.wizard')]"
#     )
