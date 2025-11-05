from odoo import models, fields, api

class FeedbackNotification(models.Model):
    _name = 'feedback.notification'
    _description = 'Feedback Notification'

    name = fields.Char(string='Name', required=True)
    feedback_status = fields.Selection([
        ('below_5', 'Below 5 Stars'),
        ('below_4', 'Below 4 Stars'),
        ('below_3', 'Below 3 Stars'),
    ], string='Feedback Rating', required=True)

    user_ids = fields.Many2many('res.users', string='Notify Users')

    @api.model
    def _register_hook(self):
        """Auto-call after model registration (no need for post_init_hook)"""
        self.env['ir.module.module'].toggle_feedback_menu()
        return super()._register_hook()

class ProjectTask(models.Model):
    _inherit = 'project.task'

    show_feedback_tab = fields.Boolean(string="Show Feedback Tab", compute="_compute_show_feedback_tab")

    def _compute_show_feedback_tab(self):
        customer_app_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'customer_app'),
            ('state', '=', 'installed')
        ]) > 0
        for task in self:
            task.show_feedback_tab = customer_app_installed

    feedback_message_ids = fields.One2many(
        'mail.message', 'res_id', compute='_compute_feedback_message_ids', string='Feedback Messages', store=False)

    def _compute_feedback_message_ids(self):
        for task in self:
            partner_ids = task.user_ids.mapped('partner_id.id')
            messages = self.env['mail.message'].search([
                ('model', '=', 'res.partner'),
                ('res_id', 'in', partner_ids),
                ('message_type', '=', 'comment'),
                ('subject', '=', "Low Customer Feedback"),
            ], order='date desc') if partner_ids else self.env['mail.message']
            task.feedback_message_ids = messages

class MenuControl(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def toggle_feedback_menu(self):
        """Enable or disable the Feedback Notification menu based on module installation."""
        module_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'customer_app'),
            ('state', '=', 'installed')
        ])

        menu = self.env.ref('industry_fsm.menu_feedback_notification', raise_if_not_found=False)
        if menu:
            menu.sudo().write({'active': bool(module_installed)})
