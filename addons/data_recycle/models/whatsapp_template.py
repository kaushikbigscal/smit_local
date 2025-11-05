import json
import re
from odoo import models, fields, api, _
import logging
import requests
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class TemplateWhatsapp(models.Model):
    _name = 'template.whatsapp'
    _description = 'Template Whatsapp'
    _rec_name = 'model_id'

    model_id = fields.Many2one('ir.model', string="Model", ondelete='cascade', required=True)
    project_id = fields.Many2one('project.project', string="Project", domain="[('is_fsm', '=', True)]")
    message = fields.Char(string="Message", help="Set dynamic message using {{task_name}} and {{stage_name}}.")
    attachment_ids = fields.Many2many('ir.attachment')
    stage_id = fields.Many2one('project.task.type', string="Stage", domain="[('id', 'in', stages_available)]")
    stages_available = fields.Many2many('project.task.type', compute="_compute_stages_available", string="Available Stages")

    @api.depends('project_id')
    def _compute_stages_available(self):
        """List only stages that belong to the selected project."""
        for record in self:
            if record.project_id:
                record.stages_available = self.env['project.task.type'].search(
                    [('project_ids', 'in', [record.project_id.id])])
            else:
                record.stages_available = False

    show_project = fields.Boolean(compute='_compute_show_project', store=True)
    show_stage = fields.Boolean(compute='_compute_show_stage', store=True)
    show_attachment = fields.Boolean(compute='_compute_show_attachment', store=True)

    @api.depends('model_id')
    def _compute_show_project(self):
        """Show project field only when 'Project' model is selected."""
        for record in self:
            if record.model_id and record.model_id.model == 'project.project':
                record.show_project = True
            else:
                record.project_id = False
                record.show_project = False

    @api.depends('project_id', 'model_id')
    def _compute_show_stage(self):
        """Show 'Stage' only if a project is selected and model is project.project."""
        for record in self:
            if record.model_id and record.model_id.model == 'project.project' and record.project_id:
                record.show_stage = True
            else:
                record.stage_id = False
                record.show_stage = False

    @api.depends('model_id')
    def _compute_show_attachment(self):
        """Show attachment field only for project model."""
        for record in self:
            if record.model_id and record.model_id.model == 'project.project':
                record.show_attachment = True
            else:
                record.attachment_ids = [(5, 0, 0)]
                record.show_attachment = False


    def action_save_template(self):
        """Save template and close form"""
        self.ensure_one()
        self.write({'message': self.message})
        return {'type': 'ir.actions.act_window_close'}

    legend_info = fields.Html(
        string="Template Variables Legend",
        readonly=True,
        sanitize=False,
        default=lambda self: _(
            """
            <div style="display: flex; gap: 30px; align-items: flex-start;">
                <!-- Service Call Group -->
                <div style="width: 50%; min-width: 300px;">
                    <h4 style="margin-bottom: 10px;">Service Call</h4>
                    <ul style="margin: 0; padding-left: 15px; line-height: 1.4;">
                        <li style="margin-bottom: 5px;"><strong>{{task_name}}</strong>: Name of the service call</li>
                        <li style="margin-bottom: 5px;"><strong>{{stage_name}}</strong>: Current stage of the service call</li>
                        <li style="margin-bottom: 5px;"><strong>{{ticket_number}}</strong>: Ticket number of the service call</li>
                        <li style="margin-bottom: 5px;"><strong>{{assignee_name}}</strong>: Assignee of the service call</li>
                        <li style="margin-bottom: 5px;"><strong>{{assignee_number}}</strong>: Assignee Mobile Number</li>
                        <li style="margin-bottom: 5px;"><strong>{{customer_name}}</strong>: Customer of the service call</li>
                        <li style="margin-bottom: 5px;"><strong>{{planned_date}}</strong>: Planned date of the service call</li>
                    </ul>
                </div>
                <!-- Leave Group -->
                <div style="width: 50%; min-width: 300px;">
                    <h4 style="margin-bottom: 10px;">Leave/Public Holidays</h4>
                    <ul style="margin: 0; padding-left: 15px; line-height: 1.4;">
                        <li style="margin-bottom: 5px;"><strong>{{customer.name}}</strong>: Customer name</li>
                        <li style="margin-bottom: 5px;"><strong>{{start_date}}</strong>: Start date</li>
                        <li style="margin-bottom: 5px;"><strong>{{end_date}}</strong>: End date</li>
                        <li style="margin-bottom: 5px;"><strong>{{next_working_date}}</strong>: Next working date</li>
                        <li style="margin-bottom: 5px;"><strong>{{name}}</strong>: Holiday Reason</li>
                        <li style="margin-bottom: 5px;"><strong>{{user_company_id_name}}</strong>: Company name</li>
                    </ul>
                </div>
            </div>
            <style>
                /* Stack vertically only on very small screens */
                @media (max-width: 550px) {
                    div[style*="display: flex"] {
                        flex-direction: column !important;
                        gap: 20px !important;
                    }
                    div[style*="width: 50%"] {
                        width: 100% !important;
                        min-width: 100% !important;
                    }
                }

                /* For very small screens, reduce spacing */
                @media (max-width: 480px) {
                    div[style*="display: flex"] {
                        gap: 15px !important;
                    }
                    div[style*="min-width: 300px"] {
                        min-width: 250px !important;
                    }
                }
            </style>
            """
        )
    )


    def send_message(self, to_number, variables=None):
        self.ensure_one()
        rendered_message = self.message or ""
        if variables and isinstance(variables, dict):
            for var_name, var_value in variables.items():
                rendered_message = rendered_message.replace(f'{{{{{var_name}}}}}', str(var_value))
                rendered_message = rendered_message.replace(f'{{{var_name}}}', str(var_value))

        if variables and 'customer' in variables:
            customer = variables['customer']
            if hasattr(customer, 'name'):
                rendered_message = rendered_message.replace('{{customer.name}}', customer.name)
                rendered_message = rendered_message.replace('{customer.name}', customer.name)

        phone_number = re.sub(r'\+\d{1,3}\s*', '', str(to_number or '')).replace(" ", "")
        print(f"Cleaned phone number: {phone_number}")

        config_data = self.get_whatsapp_configuration()
        if not config_data:
            print("No WhatsApp configuration found!")
            return
        base_url = f"http://{config_data['ip_address']}:{config_data['port']}/api/{config_data['session']}"
        try:
            token_url = f"{base_url}/{config_data['security_key']}/generate-token"
            token_response = requests.post(token_url)
            token_response.raise_for_status()
            token = token_response.json().get("token")
            if not token:
                print("Token generation failed: No token received")
                return
            print("Token generated successfully!")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"}
            message_url = f"{base_url}/send-message"
            attachment_url = f"{base_url}/send-file-base64"
            if self.attachment_ids:
                self._send_whatsapp_with_attachments(attachment_url, headers, phone_number, rendered_message, self.attachment_ids)
            else:
                self._send_whatsapp_message(message_url, headers, phone_number, rendered_message)
        except requests.exceptions.RequestException as e:
            print("WhatsApp API Request failed:", e)
        except Exception as e:
            print("Unexpected error in WhatsApp notification:", e)

    def get_whatsapp_configuration(self):
        """
        Fetch WhatsApp session, security key, IP, and port from configuration.manager.
        """
        config = self.env['manager.configuration'].search([], limit=1, order="id desc")
        if not config:
            raise UserError(_("No WhatsApp Configuration found! Please set up Configuration Manager."))
        return {
            'session': config.instance,
            'security_key': config.token,
            'ip_address': config.ip_address,
            'port': config.port }

    def _send_whatsapp_with_attachments(self, attachment_url, headers, phone_number, message, attachments):
        for attachment in attachments:
            attachment_sudo = attachment.sudo()
            if not attachment_sudo.datas:
                print(f"Attachment {attachment_sudo.name} is empty or corrupted.")
                continue
            base64_string = attachment_sudo.datas.decode('utf-8')
            file_url = f"data:{attachment_sudo.mimetype};base64,{base64_string}"
            payload = {
                "phone": phone_number,
                "isGroup": False,
                "isViewOnce": False,
                "isLid": False,
                "fileName": attachment_sudo.name,
                "caption": message,
                "base64": file_url,
                "public": True}
            response = requests.post(attachment_url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"WhatsApp attachment '{attachment.name}' sent successfully!")

    def _send_whatsapp_message(self, message_url, headers, phone_number, message):
        payload = {
            "phone": phone_number,
            "isGroup": False,
            "isNewsletter": False,
            "isLid": False,
            "message": message,
            "sanitize": False}
        response = requests.post(message_url, json=payload, headers=headers)
        response.raise_for_status()
        print("WhatsApp message sent successfully!")
