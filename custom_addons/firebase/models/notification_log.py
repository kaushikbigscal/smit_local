from odoo import models, fields, api


class NotificationLog(models.Model):
    _name = 'notification.log'
    _description = 'Notification Logs'
    _order = 'create_date desc'

    name = fields.Char(string='Event')
    description = fields.Text(string='Description')
    create_date = fields.Datetime(string='Created On', readonly=True)
    body = fields.Char(string="Body")
    title = fields.Char(string="Title")
    receiver_ids = fields.Many2many('res.users', string="Receivers")
    model = fields.Char(string="Model")
    data = fields.Char(string="Data")

    @api.model
    def create_log(self, name, title, body, receiver_ids, model, data, description):
        """Create a notification log entry"""
        return self.create({
            'name': name,
            'title': title,
            'body': body,
            'receiver_ids': [(6, 0, receiver_ids)],
            'model': model,
            'data': data,
            'description': description,

        })
