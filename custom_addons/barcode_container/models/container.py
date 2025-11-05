from odoo import models, fields, api, _
import base64
import io
import qrcode
import json
import zipfile


class Container(models.Model):
    _name = "barcode.container"
    _description = "Container"

    name = fields.Char(string="Packing List Number", required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    consignee_id = fields.Many2one("res.partner", string="Consignee")
    destination_id = fields.Many2one("stock.location", string="Destination")
    reference_nr = fields.Char("Reference Number")
    bl_nr = fields.Char("BL Number")
    fob = fields.Char("FOB")
    container_number = fields.Char("Container Number")
    date = fields.Date("Date", default=fields.Date.today)
    note = fields.Text("Note")

    line_ids = fields.One2many("barcode.container.line", "container_id", string="Species Lines")

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self.env["ir.sequence"].next_by_code("barcode.container") or _("New")
        return super().create(vals)

    def action_open_qr_scanner(self):
        """Opens QR scanner popup globally (not tied to this record)."""
        return {
            "type": "ir.actions.client",
            "tag": "open_qr_scanner_action",
        }

    def action_print_all_line_qr_labels(self):
        """Generate separate PDF for each line"""
        if not self.line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No lines found to print.',
                    'type': 'warning',
                }
            }

        # Generate PDF for each line
        report_action = self.env['ir.actions.report'].search([
            ('report_name', '=', 'barcode_container.report_single_line_qr')
        ], limit=1)

        if not report_action:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Report not found. Please check report configuration.',
                    'type': 'error',
                }
            }

        # Create a zip file containing all PDFs
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for line in self.line_ids:
                # Generate PDF for this line
                pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    'barcode_container.report_single_line_qr',
                    [line.id]
                )
                filename = f"QR_Label_{self.name}_{line.label}.pdf"
                zip_file.writestr(filename, pdf_content)

        zip_buffer.seek(0)
        zip_data = base64.b64encode(zip_buffer.read())

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'QR_Labels_{self.name}.zip',
            'type': 'binary',
            'datas': zip_data,
            'mimetype': 'application/zip',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_whole_container_report(self):
        return self.env.ref('barcode_container.action_report_container').report_action(self)


class ContainerLine(models.Model):
    _name = "barcode.container.line"
    _description = "Container Line"

    container_id = fields.Many2one("barcode.container", string="Container", required=True, ondelete="cascade")
    label = fields.Char("Label", required=True)
    species = fields.Char("Species")
    thickness_mm = fields.Float("Thickness (mm)")
    width_mm = fields.Float("Width (mm)")
    length_m = fields.Float("Length (m)")
    pieces = fields.Integer("Pieces")
    volume_m3 = fields.Float("Volume (m³)", compute="_compute_volume_m3", store=True, readonly=False, digits=(16, 4))

    @api.depends("thickness_mm", "width_mm", "length_m", "pieces")
    def _compute_volume_m3(self):
        """Compute total volume in cubic meters."""
        for line in self:
            line.volume_m3 = line._calculate_volume()

    @api.onchange("thickness_mm", "width_mm", "length_m", "pieces")
    def _onchange_volume_params(self):
        """Update volume in the form view dynamically when fields change."""
        for line in self:
            line.volume_m3 = line._calculate_volume()

    def _calculate_volume(self):
        """Helper function to calculate volume."""
        if self.thickness_mm and self.width_mm and self.length_m and self.pieces:
            thickness_m = self.thickness_mm / 1000.0
            width_m = self.width_mm / 1000.0
            return thickness_m * width_m * self.length_m * self.pieces
        return 0.0

    scanned = fields.Boolean("Scanned", default=False)

    qr_code = fields.Binary("QR Code", compute="_compute_qr_code", store=False)

    @api.depends("label", "container_id", "container_id.name")
    def _compute_qr_code(self):
        for line in self:
            if line.label and line.container_id:
                # Build full URL QR (adjust domain)
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                qr_url = f"{base_url}/barcode/container/scan?container_id={line.container_id.id}&label={line.label}"

                # Generate QR code
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(qr_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                line.qr_code = base64.b64encode(buffer.getvalue())
            else:
                line.qr_code = False

    qr_code_6_4 = fields.Binary("QR Code For 6*4 label", compute="_compute_code", store=False)

    @api.depends("label", "container_id", "container_id.name")
    def _compute_code(self):
        for line in self:
            if line.label and line.container_id:
                qr_data = json.dumps({
                    "container_id": line.container_id.id,
                    "container_name": line.container_id.name,
                    "label": line.label,
                    "species": line.species or "",
                    "pieces": line.pieces or 0,
                    "volume": line.volume_m3 or 0.0,
                })
                qr = qrcode.QRCode(box_size=3, border=1)
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                line.qr_code_6_4 = base64.b64encode(buffer.getvalue())
            else:
                line.qr_code_6_4 = False
