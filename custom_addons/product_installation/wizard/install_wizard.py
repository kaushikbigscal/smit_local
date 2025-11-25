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
