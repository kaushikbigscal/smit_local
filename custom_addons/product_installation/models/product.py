from odoo import fields, models, api

import logging

_logger = logging.getLogger(__name__)
import base64
import binascii

class Product(models.Model):
    _inherit = 'product.template'

    installed_ok = fields.Boolean(string="Can be Installed")

    installation_attachment_line_ids = fields.One2many(
        'installation.attachment.line', 'product_id', string='Attachments', store=True, tracking=True)

    enable_distributor = fields.Boolean(
        string="Distributor Enabled",
        compute='_compute_enable_distributor',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'product_installation.enable_distributor', 'False'
        ) == 'True'
    )

    @api.depends()
    def _compute_enable_distributor(self):
        param_value = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor', 'False')
        for product in self:
            product.enable_distributor = (param_value == 'True')


class AmcAttachmentLine(models.Model):
    _name = 'installation.attachment.line'
    _description = 'Attachment Line'

    name = fields.Char('Description', store=True, required=True)
    upload_file = fields.Binary(string='Upload Document', store=True)
    product_id = fields.Many2one('product.template', string='Product', ondelete='cascade')
    upload_file_filename = fields.Char('File Name')

    ir_attachment_id = fields.Many2one('ir.attachment', string="Chatter Attachment", copy=False)

    # ---------- Sync with chatter ----------
    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Only create ir.attachment if this wasn't created from ir.attachment sync
        if not self.env.context.get('from_ir_attachment'):
            record._create_ir_attachment()
        return record

    def write(self, vals):
        res = super().write(vals)
        # Only update ir.attachment if this wasn't triggered by ir.attachment sync
        if not self.env.context.get('from_ir_attachment'):
            for rec in self:
                rec._create_ir_attachment()
        return res

    def unlink(self):
        if self.env.context.get('skip_attachment_unlink'):
            return super().unlink()
        for rec in self:
            if rec.ir_attachment_id:
                rec.ir_attachment_id.with_context(skip_product_unlink=True).unlink()
        return super().unlink()

    def _create_ir_attachment(self):
        for rec in self:
            if rec.upload_file and rec.product_id:
                filename = rec.upload_file_filename or rec.name or "Attachment"
                datas = rec.upload_file

                # Skip if datas is empty
                if not datas:
                    _logger.warning("Skipping empty attachment for %s", filename)
                    continue

                # Validate base64
                try:
                    # Ensure it's valid Base64
                    base64.b64decode(datas, validate=True)
                except (binascii.Error, ValueError):
                    _logger.warning("Skipping invalid Base64 for %s", filename)
                    continue

                if rec.ir_attachment_id:
                    # Update existing attachment
                    rec.ir_attachment_id.with_context(skip_product_sync=True).sudo().write({
                        'name': filename,
                        'datas': datas,
                    })
                else:
                    # Create new attachment safely
                    attachment = self.env['ir.attachment'].with_context(skip_product_sync=True).create({
                        'name': filename,
                        'type': 'binary',
                        'datas': datas,
                        'res_model': 'product.template',
                        'res_id': rec.product_id.id,
                        'mimetype': 'application/octet-stream',
                    })
                    rec.with_context(from_ir_attachment=True).write({'ir_attachment_id': attachment.id})


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def unlink(self):
        if self.env.context.get('skip_product_unlink'):
            return super().unlink()
        for attachment in self:
            lines = self.env['installation.attachment.line'].search([('ir_attachment_id', '=', attachment.id)])
            lines.with_context(skip_attachment_unlink=True).unlink()
        return super().unlink()

    def write(self, vals):
        res = super().write(vals)
        # Only sync back to installation.attachment.line if not triggered by it
        if not self.env.context.get('skip_product_sync'):
            for attachment in self:
                if attachment.res_model == 'product.template' and attachment.res_id:
                    lines = self.env['installation.attachment.line'].search([('ir_attachment_id', '=', attachment.id)])
                    if lines:
                        lines.with_context(from_ir_attachment=True).write({
                            'name': attachment.name or 'Attachment',
                            'upload_file': attachment.datas,
                            'upload_file_filename': attachment.name,
                        })
        return res

    @api.model
    def create(self, vals):
        attachment = super().create(vals)

        # Only sync if it's attached to a product.template and not triggered by installation.attachment.line
        if (attachment.res_model == 'product.template' and
                attachment.res_id and
                not self.env.context.get('skip_product_sync')):
            product = self.env['product.template'].browse(attachment.res_id)

            # Create with context to prevent circular sync
            self.env['installation.attachment.line'].with_context(from_ir_attachment=True).create({
                'name': attachment.name or 'Attachment',
                'upload_file': attachment.datas,
                'upload_file_filename': attachment.name,
                'product_id': product.id,
                'ir_attachment_id': attachment.id,
            })

        return attachment


class ProductCategory(models.Model):
    _inherit = 'product.category'

    installed_ok = fields.Boolean(string="Can be Installed")

    installation_attachment_line_ids = fields.One2many(
        'installation.attachment.line', 'product_id', string='Attachments', store=True, tracking=True)

    enable_distributor = fields.Boolean(
        string="Distributor Enabled",
        compute='_compute_enable_distributor',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'product_installation.enable_distributor', 'False'
        ) == 'True'
    )

    @api.depends()
    def _compute_enable_distributor(self):
        param_value = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor', 'False')
        for product in self:
            product.enable_distributor = (param_value == 'True')

class ProjectTask(models.Model):
    _inherit = 'project.task'

    installation_table_html = fields.Html(
        string="Installation Info",
        sanitize=True,
        readonly=True,
    )
    enable_distributor = fields.Boolean(
        string="Is Distributor",
        default=lambda self: bool(
            self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor', False)
        )
    )
    installation_request_confirmed = fields.Boolean(
        string="Installation Request Confirmed",
        default=False
    )    
