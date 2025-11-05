import base64

from odoo import models, fields
import xml.etree.ElementTree as ET

from odoo.exceptions import UserError


class XmlUpload(models.Model):
    _name = 'xml.upload'
    _description = 'Uploaded XML File'

    name = fields.Char("Filename")
    xml_file = fields.Binary("Document/Report", required=True)
    xml_content = fields.Text("XML Content" ,readonly=False)
    model_id = fields.Many2one('ir.model', string='Target Model')
    # report_config_id = fields.Many2one('xml.upload', string='Report Template', required=True)
    report_action = fields.Selection([
        ('action_xml_upload_custom_report_format_for_all', 'Employee PaySlip Report'),
        ('action_xml_upload_custom_report_format_for_all_service_call', 'Service Call Detailed report'),
        ('action_xml_upload_custom_report_format_for_all_account_move_invoice', 'Invoice Report'),
        ('action_xml_upload_custom_report_format_for_all_sale_order', 'Quotation/Order Report'),
        ('action_xml_upload_custom_report_format_for_all_amc_contract', 'AMC Contract Report'),
        ('action_xml_upload_custom_report_format_for_all_cmc_contract', 'CMC Contract Report'),
    ], string="Report Type", required=True)

    def parse_xml(self, xml_data):
        try:

            self.xml_content = xml_data.decode('utf-8')
            print(self.xml_content)
        except ET.ParseError as e:
            raise ValueError(f"XML Parse Error: {str(e)}")



    def upload_and_parse_xml(self):
        if self.xml_file:
            xml_data = base64.b64decode(self.xml_file)
            print(xml_data)
            self.parse_xml(xml_data)
        else:
            raise ValueError("No XML file uploaded")

    # added to get unique view
    def get_or_create_customizer_view(self):
        self.ensure_one()
        # Remove XML declaration if present
        xml_content = self.xml_content.strip()
        if xml_content.startswith('<?xml'):
            xml_content = xml_content.split('?>', 1)[1].strip()
        view_xml_id = f'data_recycle.report_template_service_call_xml_upload_{self.id}'
        view = self.env['ir.ui.view'].search([('key', '=', view_xml_id)], limit=1)
        if not view:
            view = self.env['ir.ui.view'].create({
                'name': view_xml_id,
                'key': view_xml_id,
                'model': self.model_id.model,
                'type': 'qweb',
                'arch_db': xml_content,
            })
        else:
            view.arch_db = xml_content
        return view

    def download_report(self):
        self.ensure_one()

        if not self.model_id:
            raise UserError("Please select a model.")

        model = self.model_id.model
        record_model = self.env[self.model_id.model]
        if model == 'hr.payslip':
            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()

                if self.report_action == 'action_xml_upload_custom_report_format_for_all':

                    view = self.env.ref('data_recycle.report_template_xml_upload')
                    view.arch_db = xml_content
                    view.write({'arch_db': xml_content})
                    report_action = 'data_recycle.action_xml_upload_custom_report_format_for_all'

            target_record = record_model.search([], limit=1)

        elif model == 'project.task':
            # Use unique view for each customizer
            view = self.get_or_create_customizer_view()
            # Create or get a report action for this view
            report_xml_id = f'data_recycle.action_custom_report_service_call_{self.id}'
            report_action_obj = self.env['ir.actions.report'].search([
                ('report_name', '=', view.key),
                ('model', '=', 'project.task'),
            ], limit=1)
            if not report_action_obj:
                report_action_obj = self.env['ir.actions.report'].create({
                    'name': f'Custom Service Call Report {self.name}',
                    'model': 'project.task',
                    'report_type': 'qweb-pdf',
                    'report_name': view.key,
                    'report_file': view.key,
                })
            report_action = report_action_obj.xml_id or report_action_obj.id
            target_record = record_model.search([], limit=1)

        elif model == 'account.move':

            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()
                view = self.env.ref('data_recycle.report_template_xml_upload_account_move_invoice')
                view.arch_db = xml_content
                view.write({'arch_db': xml_content})
            report_action = 'data_recycle.action_xml_upload_custom_report_format_for_all_account_move_invoice'
            target_record = record_model.search([], limit=1)

        elif model == 'sale.order':
            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()

                view = self.env.ref('data_recycle.report_template_xml_upload_sale_order')
                view.arch_db = xml_content
                view.write({'arch_db': xml_content})
            report_action = 'data_recycle.action_xml_upload_custom_report_format_for_all_sale_order'
            target_record = record_model.search([], limit=1)

        elif model == 'amc.contract':
            if self.report_action == 'action_xml_upload_custom_report_format_for_all_amc_contract':
                # AMC logic
                if self.xml_content:
                    xml_content = self.xml_content.strip()
                    if xml_content.startswith('<?xml'):
                        xml_content = xml_content.split('?>', 1)[1].strip()
                    view = self.env.ref('data_recycle.report_template_xml_upload_amc_contract')
                    view.arch_db = xml_content
                    view.write({'arch_db': xml_content})
                report_action = 'data_recycle.action_xml_upload_custom_report_format_for_all_amc_contract'
                target_record = record_model.search([], limit=1)

            elif self.report_action == 'action_xml_upload_custom_report_format_for_all_cmc_contract':
                # CMC logic
                if self.xml_content:
                    xml_content = self.xml_content.strip()
                    if xml_content.startswith('<?xml'):
                        xml_content = xml_content.split('?>', 1)[1].strip()
                    view = self.env.ref('data_recycle.report_template_xml_upload_cmc_contract')
                    view.arch_db = xml_content
                    view.write({'arch_db': xml_content})
                report_action = 'data_recycle.action_xml_upload_custom_report_format_for_all_cmc_contract'
                target_record = record_model.search([], limit=1)
        else:
            raise UserError("No report action defined for the selected report template.")

        # return self.env.ref(report_action).report_action(target_record)
        if isinstance(report_action, str):
            report_obj = self.env.ref(report_action)
        else:
            report_obj = self.env['ir.actions.report'].browse(report_action)
        return report_obj.report_action(target_record)
