from odoo import models, fields
#
# class Automate(models.Model):
#     _inherit = 'project.project'
#
#     def write(self, values):
#         if 'stage_id' in values:
#             stage_done = self.env.ref('project.last_update_status=done')
#
#             if values['stage_id'] == stage_done.id:
#                 for project in self:
#                     tasks = self.env['project.task'].search([('project_id', '=', project.id)])
#                     tasks.write({'stage_id': stage_done.id})
#
#         return super(Automate, self).write(values)

import logging

_logger = logging.getLogger(__name__)

class Automate(models.Model):
    _inherit = 'project.project'

    def write(self, values):
        _logger.info("Writing values: %s", values)  # Log the incoming values
        if 'stage_id' in values:
            stage_done = self.env.ref('project.stage_done')
            print(stage_done.id)

            if values['stage_id'] == stage_done.id:
                for project in self:
                    tasks = self.env['project.task'].search([('project_id', '=', project.id)])
                    tasks.write({'stage_id': stage_done.id})
                    _logger.info("Marked tasks as done for project: %s", project.name)

        return super(Automate, self).write(values)
