# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
from odoo.exceptions import UserError
from odoo.fields import Command, _logger
from odoo.http import request
import json

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    display_in_catalog = fields.Boolean(string="Is Feature Set")

class ProductCategory(models.Model):
    _inherit = 'product.category'

    display_in_catalog_category = fields.Boolean(string="Is Feature Set")

class PortalWizardInherit(models.TransientModel):
    _inherit = 'portal.wizard'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Partners',
        default=lambda self: self._default_partner_ids()  # updated reference
    )

    def _default_partner_ids(self):
        partner_ids = self.env.context.get('default_partner_ids', []) or self.env.context.get('active_ids', [])
        return [Command.link(pid) for pid in partner_ids]


class PortalWizardUser(models.TransientModel):
    _inherit = 'portal.wizard.user'

    def action_grant_access(self):
        self.ensure_one()

        # Your custom logic before calling super
        company = self.partner_id.company_id or self.env.company
        if not company.enable_customer_portal:
            raise UserError(_(
                "Cannot grant portal access to '{}' because their company has not enabled Customer Portal access."
            ).format(self.partner_id.name))

        # Call original logic
        return super().action_grant_access()

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    ticket_id = fields.Many2one('project.task', string="Related Ticket")
