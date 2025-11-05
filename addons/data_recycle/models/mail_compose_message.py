from odoo import models, api
import base64

class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.model
    def _get_pdf_attachment(self, res_model, res_id):
        """Return (filename, pdf_bytes) for the payslip, custom or default."""
        if res_model == 'hr.payslip':
            payslip = self.env[res_model].browse(res_id)
            # Check for customizer
            customizer = self.env['xml.upload'].search([
                ('model_id.model', '=', 'hr.payslip'),
                ('report_action', '=', 'action_xml_upload_custom_report_format_for_all'),
                ('xml_file', '!=', False),
            ], limit=1)
            if customizer and customizer.xml_file:
                pdf = self.env.ref("data_recycle.action_xml_upload_custom_report_format_for_all")._render_qweb_pdf(payslip.id)[0]
                filename = f"Payslip Details - {payslip.employee_id.name or 'Payslip'}.pdf"
                return filename, pdf
            else:
                # Default report
                pdf = self.env.ref("om_hr_payroll.payslip_details_report")._render_qweb_pdf(payslip.id)[0]
                filename = f"Payslip Details - {payslip.employee_id.name or 'Payslip'}.pdf"
                return filename, pdf
        return None, None

    @api.model
    def generate_email_for_composer(self, template_id, res_ids):
        results = super().generate_email_for_composer(template_id, res_ids)
        ctx = self.env.context
        res_model = ctx.get('default_model')
        if res_model == 'hr.payslip':
            for res_id in res_ids:
                filename, pdf = self._get_pdf_attachment(res_model, res_id)
                if filename and pdf:
                    # Attach PDF
                    attachment = self.env['ir.attachment'].create({
                        'name': filename,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf),
                        'res_model': res_model,
                        'res_id': res_id,
                        'mimetype': 'application/pdf'
                    })
                    if res_id in results:
                        results[res_id]['attachments'] = [(attachment.name, base64.b64decode(attachment.datas))]
        return results 