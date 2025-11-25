import base64
import binascii

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=False, change_default=True, index=True,
        tracking=1,
       )

    installation_line_ids = fields.One2many(
        'sale.order.installation.line',
        'order_id',
        string='Installation Attachments',
    )

    sale_order_type = fields.Selection([
        ('primary_orders', 'Primary Orders'),
        ('secondary_orders', 'Secondary Orders'),
        ('direct_orders', 'Direct Orders'),
    ], default='direct_orders')

    distributor_id = fields.Many2one('res.partner', domain=[('company_type', '=', 'distribution')])

    enable_distributor = fields.Boolean(
        string="Is Distributor",
        default=lambda self: bool(
            self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor', False)
        )
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', required=True,
        compute='_compute_warehouse_id', store=True, readonly=False, precompute=True,
        check_company=True)


    installation_table_html = fields.Html(
        string="Installation Info",
        sanitize=True,
        readonly=True,
    )

    @api.constrains('sale_order_type', 'partner_id', 'distributor_id')
    def _check_required_fields(self):
        for order in self:
            if order.sale_order_type == 'primary_orders':
                if not order.distributor_id:
                    raise ValidationError(_("Distributor is required for Primary Orders."))

            elif order.sale_order_type == 'secondary_orders':
                if not order.partner_id and not order.distributor_id:
                    raise ValidationError(_("Distributor and Customer is required for Secondary Orders."))
                if not order.partner_id:
                    raise ValidationError(_("Customer is required for Secondary Orders."))
                if not order.distributor_id:
                    raise ValidationError(_("Distributor is required for Secondary Orders."))

            elif order.sale_order_type == 'direct_orders':
                if not order.partner_id:
                    raise ValidationError(_("Customer is required for Direct Orders."))

    @api.depends('sale_order_type', 'distributor_id', 'user_id', 'company_id')
    def _compute_warehouse_id(self):

        """Override main compute to use distributor warehouse for secondary orders"""
        for order in self:
            if order.sale_order_type == 'secondary_orders' and order.distributor_id:
                # Use distributor warehouse
                order.warehouse_id = order.distributor_id.warehouse_id.id or False
            else:
                # fallback to default logic from main compute
                default_warehouse_id = self.env['ir.default'].with_company(
                    order.company_id.id)._get_model_defaults('sale.order').get('warehouse_id')
                if order.state in ['draft', 'sent'] or not order.ids:
                    if default_warehouse_id is not None:
                        order.warehouse_id = default_warehouse_id
                    else:
                        order.warehouse_id = order.user_id.with_company(
                            order.company_id.id)._get_default_warehouse_id()


    @api.onchange('sale_order_type', 'distributor_id')
    def _onchange_order_distributor(self):
        """
         primary and secondary orders:
        - Primary order: set company_id, partner_invoice_id, partner_shipping_id
        - Secondary order: set company_id
        - Reset partner info if not primary
        """
        for order in self:
            # Primary order logic
            if order.sale_order_type == 'primary_orders' and order.distributor_id:
                if order.distributor_id.company_id:
                    order.company_id = order.distributor_id.company_id.id
                # Set invoice and shipping addresses to distributor
                order.partner_invoice_id = order.distributor_id
                order.partner_shipping_id = order.distributor_id

            # Secondary order logic
            elif order.sale_order_type == 'secondary_orders' and order.distributor_id:
                distributor_company = order.distributor_id.company_id
                if distributor_company:
                    order.company_id = distributor_company.id

            # Reset partner info for other order types
            elif order.partner_id:
                order.partner_invoice_id = order.partner_id
                order.partner_shipping_id = order.partner_id

            if order.sale_order_type == 'secondary_orders':
                if order.distributor_id and order.distributor_id.user_id:
                    order.user_id = order.distributor_id.user_id
                else:
                    order.user_id = self.env.user

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._generate_installation_lines()


        return orders

    def write(self, vals):
        res = super().write(vals)

        # Regenerate installation lines if order lines changed
        if 'order_line' in vals:
            self._generate_installation_lines()

        return res

    def _generate_installation_lines(self):
        """Generate installation lines and ir.attachments without duplication."""
        for order in self:
            # 1️⃣ Get existing Checklist attachments for this order
            existing_files = set(
                self.env['ir.attachment'].search([
                    ('res_model', '=', 'sale.order'),
                    ('res_id', '=', order.id),
                    ('name', 'like', 'Checklist')
                ]).mapped('name')
            )

            # 2️⃣ Track already existing installation lines by product template
            existing_templates = order.installation_line_ids.mapped('product_id')
            existing_template_ids = {tmpl.id for tmpl in existing_templates}

            attachment_vals = []
            new_lines = []

            # 3️⃣ Process unique product templates only
            templates = order.order_line.mapped('product_id.product_tmpl_id')
            for tmpl in templates:
                if tmpl.id in existing_template_ids:
                    continue  # Skip templates already added

                attachments = tmpl.installation_attachment_line_ids
                if not attachments and tmpl.categ_id.installed_ok:
                    attachments = tmpl.categ_id.installation_attachment_line_ids

                valid_attachments = attachments.filtered(lambda a: a.upload_file)
                for attach in valid_attachments:
                    try:
                        base64.b64decode(attach.upload_file, validate=True)
                    except (binascii.Error, ValueError):
                        continue

                    # 4️⃣ Add new installation line
                    new_lines.append((0, 0, {
                        'product_id': tmpl.id,
                        'attachment_id': attach.id,
                        'attachment_name': attach.name,
                        'file': attach.upload_file,
                        'file_name': attach.upload_file_filename,
                        'product_display_name': tmpl.display_name,
                    }))

                    # 5️⃣ Only create ir.attachment if not already existing
                    filename = f"Checklist - {tmpl.name} - {attach.upload_file_filename or attach.name or 'Attachment'}"
                    if filename not in existing_files:
                        attachment_vals.append({
                            'name': filename,
                            'type': 'binary',
                            'datas': attach.upload_file,
                            'res_model': 'sale.order',
                            'res_id': order.id,
                            'mimetype': 'application/octet-stream',
                        })
                        existing_files.add(filename)

            # 6️⃣ Add new installation lines without touching existing ones
            if new_lines:
                order.installation_line_ids = [(0, 0, line[2]) for line in new_lines] + [(4, line.id) for line in
                                                                                         order.installation_line_ids]

            # 7️⃣ Create attachments in batch
            if attachment_vals:
                self.env['ir.attachment'].create(attachment_vals)

    def action_quotation_send(self):
        """Keep default quotation PDF + add ir.attachment files of sale.order."""
        self.ensure_one()
        action = super().action_quotation_send()
        ctx = dict(action.get("context", {}))

        extra_attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.id),
            ('name', 'like', 'Checklist'),
        ])
        if extra_attachments:
            ctx['extra_sale_order_attachment_ids'] = extra_attachments.ids

        action['context'] = ctx
        return action


    def action_confirm(self):
        res = super().action_confirm()

        for order in self:

            enabled = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
            if not enabled:
                continue

            distributor_warehouse = order.distributor_id.warehouse_id if order.distributor_id else False
            if not distributor_warehouse:
                continue

            for picking in order.picking_ids:

                moves = picking.move_ids_without_package  # updated field
                if order.sale_order_type == 'primary_orders':
                    picking.location_dest_id = distributor_warehouse.lot_stock_id.id
                    picking.partner_id = False
 
                    for move in moves:
                        move.location_dest_id = distributor_warehouse.lot_stock_id.id

                elif order.sale_order_type == 'secondary_orders':
                    picking.location_id = distributor_warehouse.lot_stock_id.id
                    for move in moves:
                        move.location_id = distributor_warehouse.lot_stock_id.id
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    distributor_asset = fields.Many2one('distributor.asset', string="Distributor Asset")

    is_distributor = fields.Boolean(
        string="Is Distributor",
        compute="_compute_is_distributor",
        store=True,
    )
    is_installation = fields.Boolean(string="Is Installation required",store=True,compute="_compute_is_installation")

    enable_distributor = fields.Boolean(
        string="Is Distributor",
        default=lambda self: bool(
            self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor', False)
        )
    )

    @api.depends("order_id.sale_order_type")
    def _compute_is_distributor(self):
        for line in self:
            line.is_distributor = line.order_id.sale_order_type == "secondary_orders"


    @api.depends(
        "order_id.sale_order_type",
        "product_id.installed_ok",
        "product_template_id.installed_ok"
    )
    def _compute_is_installation(self):
        for line in self:
            if line.order_id.sale_order_type == "primary_orders":
                # If primary order, installation is not required
                line.is_installation = False
            else:
                # Otherwise, check installed_ok flag
                line.is_installation = (line.product_id and line.product_id.installed_ok) or \
                                       (line.product_template_id and line.product_template_id.installed_ok)

    def action_open_installation_wizard(self):
        """Open installation wizard for this sale order line"""
        self.ensure_one()
        return {
            'name': _('Installation Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'installation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_order_id': self.order_id.id,
            },
        }

    product_template_domain_ids = fields.Many2many(
        "product.template",
        compute="_compute_product_template_domain_ids",
        store=False,
    )

    @api.depends("is_distributor", "order_id.distributor_id")
    def _compute_product_template_domain_ids(self):
        for rec in self:
            if rec.is_distributor and rec.order_id.distributor_id:
                # Filter distributor.asset by the selected distributor
                asset_products = self.env["distributor.asset"].search([
                    ("distributor_id", "=", rec.order_id.distributor_id.id),("status", "=", "unallocated")
                ]).mapped("product_id").ids
                rec.product_template_domain_ids = [(6, 0, asset_products)]
            else:
                # Normal products (sale_ok)
                products = self.env["product.template"].search([("sale_ok", "=", True)]).ids
                rec.product_template_domain_ids = [(6, 0, products)]

    product_domain_ids = fields.Many2many(
        "product.product", compute="_compute_product_domain_ids", store=False
    )

    @api.depends("is_distributor")
    def _compute_product_domain_ids(self):
        for line in self:
            if line.is_distributor:
                # only products linked with distributor.asset
                distributor_templates = self.env["distributor.asset"].search(
                    [("distributor_id", "=", line.order_id.distributor_id.id),("status", "=", "unallocated")]).mapped("product_id").ids
                products = self.env["product.product"].search([("product_tmpl_id", "in", distributor_templates)])
                line.product_domain_ids = products
            else:
                # all active products
                line.product_domain_ids = self.env["product.product"].search([("active", "=", True)])


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    @api.onchange("template_id")
    def _onchange_template_id_add_extra(self):
        extra_ids = self._context.get("extra_sale_order_attachment_ids") or []
        if extra_ids:
            merged = list(set(self.attachment_ids.ids + extra_ids))
            self.attachment_ids = [(6, 0, merged)]


class SaleOrderInstallationLine(models.Model):
    _name = 'sale.order.installation.line'
    _description = 'Sale Order Installation Line'

    order_id = fields.Many2one('sale.order', ondelete='cascade')
    sale_line_id = fields.Many2one('sale.order.line', ondelete='cascade')
    product_id = fields.Many2one('product.template', ondelete='cascade')
    attachment_id = fields.Many2one('installation.attachment.line', ondelete='cascade')
    attachment_name = fields.Char()
    file = fields.Binary()
    file_name = fields.Char()
    product_display_name = fields.Char(string="Product Name in Order")

from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)



class InstallationWizard(models.TransientModel):
    _name = 'installation.wizard'
    _description = 'Installation Wizard'

    order_id = fields.Many2one('sale.order', string="Order", readonly=True)
    order_line_id = fields.Many2one('sale.order.line', string="Order Line", readonly=True)
    product_id = fields.Many2one('product.product', string="Product", readonly=True)

    attachment_name = fields.Char(string="Attachment Name")
    file = fields.Binary(string="File")
    file_name = fields.Char(string="File Name")

    installation_table_html = fields.Html(string="Installation Table", readonly=True, sanitize=True)

    def _get_dynamic_field_values(self):
        """Fetch all dynamic fields for this wizard and their current values"""
        DynamicField = self.env['dynamic.fields']
        dynamic_fields = DynamicField.search([
            ('model_id.model', '=', self._name)
        ])
        result = []
        for df in dynamic_fields:
            field_name = df.name
            if field_name in self._fields:
                result.append({
                    'label': df.field_description or field_name,
                    'value': getattr(self, field_name) or "",
                })
        return result

    def _build_installation_table_html(self):
        """Build HTML with attachments first, then dynamic fields pivoted by product per order line (sale_line_id hidden)"""
        InstallationLine = self.env['sale.order.installation.line']
        lines = InstallationLine.search([('order_id', '=', self.order_id.id)])

        html = ""

        # --- Attachment Table ---
        attachment_lines = lines.filtered(lambda l: l.file)
        if attachment_lines:
            html += """
            <h4>Attachments</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Attachment Name</th>
                        <th style="padding:6px; text-align:left;">File</th>
                        <th style="padding:6px; text-align:left;">Product</th>
                    </tr>
                </thead>
                <tbody>
            """
            for line in attachment_lines:
                file_link = f'/web/content/sale.order.installation.line/{line.id}/file/{line.file_name}?download=true' if line.file else ""
                file_link_html = f'<a href="{file_link}">{line.file_name or "Download"}</a>' if file_link else ""
                html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600;">{line.attachment_name}</td>
                        <td style="padding:6px;">{file_link_html}</td>
                        <td style="padding:6px;">{line.product_display_name or ""}</td>
                    </tr>
                """
            html += "</tbody></table>"

        # --- Dynamic Field Table ---
        dynamic_lines = lines.filtered(lambda l: not l.file)
        if dynamic_lines:
            # All unique field labels
            field_labels = list({l.attachment_name for l in dynamic_lines})
            field_labels.sort()

            # Group by sale_line_id (or line.id if no sale_line)
            line_groups = {}
            for line in dynamic_lines:
                key = line.sale_line_id.id if line.sale_line_id else line.id
                if key not in line_groups:
                    line_groups[key] = {
                        'product_name': line.product_id.display_name if line.product_id else "Unknown Product",
                        'fields': {}
                    }
                line_groups[key]['fields'][line.attachment_name] = line.product_display_name or ""

            # Build table without showing sale_line_id
            html += """
            <h4>Custom Fields</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Product</th>
            """
            for label in field_labels:
                html += f"<th style='padding:6px; text-align:left;'>{label}</th>"
            html += "</tr></thead><tbody>"

            for data in line_groups.values():
                html += "<tr style='border-bottom:1px solid #eee;'>"
                html += f"<td style='padding:6px; font-weight:600;'>{data['product_name']}</td>"
                for label in field_labels:
                    html += f"<td style='padding:6px;'>{data['fields'].get(label, '')}</td>"
                html += "</tr>"

            html += "</tbody></table>"

        # Save HTML to order (auto-updates)
        self.order_id.installation_table_html = html

    def action_save_dynamic_fields(self):
        """Save attachments and dynamic fields, then rebuild HTML table"""
        self.ensure_one()
        InstallationLine = self.env['sale.order.installation.line']
        order_line = self.order_line_id
        product_template = self.product_id.product_tmpl_id if self.product_id else False

        if not product_template:
            return

        # --- Save attachment ---
        if self.attachment_name or self.file:
            vals = {
                'order_id': self.order_id.id,
                'sale_line_id': order_line.id,
                'product_id': product_template.id,
                'attachment_name': self.attachment_name,
                'file': self.file,
                'file_name': self.file_name,
                'product_display_name': product_template.display_name,
            }
            line = InstallationLine.search([
                ('order_id', '=', self.order_id.id),
                ('sale_line_id', '=', order_line.id),
                ('product_id', '=', product_template.id),
                ('attachment_name', '=', self.attachment_name),
            ], limit=1)
            if line:
                line.write(vals)
            else:
                InstallationLine.create(vals)

            # Add attachment to chatter
            if self.file:
                self.order_id.message_post(
                    body=f"Added installation attachment: {self.attachment_name}",
                    attachments=[(self.file_name, self.file)]
                )

        # --- Save dynamic fields ---
        dynamic_values = self._get_dynamic_field_values()
        for item in dynamic_values:
            vals = {
                'order_id': self.order_id.id,
                'sale_line_id': order_line.id,
                'product_id': product_template.id,
                'attachment_name': item['label'],
                'file': False,
                'file_name': False,
                'product_display_name': item['value'],
            }
            existing_line = InstallationLine.search([
                ('order_id', '=', self.order_id.id),
                ('sale_line_id', '=', order_line.id),
                ('product_id', '=', product_template.id),
                ('attachment_name', '=', item['label']),
            ], limit=1)
            if existing_line:
                existing_line.write(vals)
            else:
                InstallationLine.create(vals)

        # --- Rebuild HTML table ---
        self._build_installation_table_html()

