from odoo import fields, models


class WhatsappAuthenticate(models.TransientModel):
    """Create a new model"""
    _name = 'authenticate.whatsapp'
    _description = 'Whatsapp Authentication Wizard'

    qrcode = fields.Binary(attachment=False, string="Qr Code",
                           help="QR code for scanning")
    configuration_manager_id = fields.Many2one("manager.configuration",
                                               string="Configuration Manager",
                                               help="Configuration manager"
                                                    "details")

    def action_save(self):
        """ Action for Save Button which will check Authentication"""
        self.configuration_manager_id.action_authenticate()