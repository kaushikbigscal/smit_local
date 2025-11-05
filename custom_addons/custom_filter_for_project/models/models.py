from odoo import models


class ProjectTaskInherited(models.Model):
    _inherit = 'project.task'

    def get_private_task_ids(self):
        """
        Return a list of task IDs that the current user created, assigned to themselves,
        and are not assigned to other users.
        """
        current_user_id = self.env.uid
        excluded_user_ids = self.env['res.users'].search([('id', '!=', current_user_id)]).ids
        tasks = self.search([
            ('create_uid', '=', current_user_id),
            ('user_ids', '=', current_user_id),
            ('user_ids', '!=', False),
            ('user_ids', 'not in', excluded_user_ids)
        ])
        return tasks.ids

    def get_assigned_by_me_task_ids(self):
        """
        Return a list of task IDs created by the current user but assigned to other users.
        """
        current_user_id = self.env.uid
        excluded_user_ids = self.env['res.users'].search([('id', '!=', current_user_id)]).ids
        tasks = self.search([
            ('create_uid', '=', current_user_id),
            ('user_ids', '!=', False),
            ('user_ids', 'in', excluded_user_ids)
        ])
        return tasks.ids
