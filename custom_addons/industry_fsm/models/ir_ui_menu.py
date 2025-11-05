# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _
from odoo.exceptions import AccessError


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if not self.env.user.has_group('industry_fsm.group_fsm_manager'):
            res.append(self.env.ref('industry_fsm.fsm_menu_reporting_customer_ratings').id)
        return res

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def unlink(self):
        for attachment in self:
            # Only check for attachments linked to project.task
            if attachment.res_model == 'project.task' and attachment.res_id:
                task = self.env['project.task'].browse(attachment.res_id)
                # Skip if the task is being deleted or doesn't exist
                if task.exists() and task.is_fsm and not self.env.user.has_group('industry_fsm.group_fsm_manager'):
                    raise AccessError(_("You cannot delete this attachment linked to a service call."))
        return super().unlink()