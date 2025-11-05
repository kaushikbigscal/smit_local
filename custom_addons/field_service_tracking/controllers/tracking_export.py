import io
from odoo import http
from odoo.http import request
import xlsxwriter
from datetime import datetime


class GpsTrackingExportController(http.Controller):

    @http.route('/gps/tracking/export', type='http', auth='user')
    def export_tracking(self, ids=None, **kwargs):
        ids = [int(x) for x in ids.split(',')] if ids else []
        records = request.env['gps.tracking'].browse(ids)

        # Create in-memory file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Tracking Logs")

        # Header style
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        # Normal cell style
        text_format = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})

        headers = [
            "Lead Name", "Customer", "Phone", "Mobile", "Customer Address",
            "Timestamp", "Employee", "Tracking Type",
            "Tracking Address", "Lat/Long"
        ]

        # Track column max widths
        col_widths = [len(h) for h in headers]

        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data rows
        for row, log in enumerate(records, start=1):
            # Resolve source display and partner dynamically
            source = ''
            partner = None
            if log.link_id:
                source = log.link_id.display_name or ''
                try:
                    linked = request.env[log.link_id.model].sudo().browse(log.link_id.res_id)
                    if linked.exists():
                        # Try common partner fields
                        partner_field_candidates = (
                            'partner_id', 'customer_id', 'commercial_partner_id',
                            'partner', 'res_partner_id', 'contact_id'
                        )
                        for fname in partner_field_candidates:
                            if hasattr(linked, fname):
                                val = getattr(linked, fname)
                                if val:
                                    partner = val
                                    break
                except Exception:
                    partner = None
            # Merge Lat + Long
            coordinates = ""
            if log.latitude and log.longitude:
                coordinates = "{:.8f}, {:.8f}".format(log.latitude, log.longitude)
            elif log.latitude:
                coordinates = "{:.8f}".format(log.latitude)
            elif log.longitude:
                coordinates = "{:.8f}".format(log.longitude)
            values = [
                source,
                partner.name if partner else "",
                partner.phone if partner else "",
                partner.mobile if partner else "",
                (partner.contact_address if partner else "").replace("\n", ", "),
                str(log.timestamp or ""),
                log.employee_id.name or "",
                dict(log._fields['tracking_type'].selection).get(log.tracking_type, ""),
                log.address if log.address else "",
                coordinates
            ]

            for col, val in enumerate(values):
                worksheet.write(row, col, val, text_format)
                col_widths[col] = max(col_widths[col], len(str(val)))

        # Auto-fit columns (with small padding)
        for col, width in enumerate(col_widths):
            worksheet.set_column(col, col, min(width + 2, 50))  # cap at 50 chars

        workbook.close()
        output.seek(0)

        # Send response
        filename = f"gps_tracking_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
