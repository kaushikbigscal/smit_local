from odoo import models, api, exceptions
import logging

_logger = logging.getLogger(__name__)
class ProjectTask(models.Model):
    _inherit = 'project.task'

# stage restriction

    # @api.model
    # def write(self, vals):
    #     # Check if the stage is being changed          and if we have to restrict state we can changed stage_id value to state
    #     if 'stage_id' in vals:
    #
    #         # Get the project manager of the task's project and current user
    #         project_manager = self.project_id.user_id
    #         current_user = self.env.user
    #
    #         # Check if the current user is the project manager
    #         if current_user != project_manager:
    #             raise exceptions.UserError("Only the project manager can change the stage of this task.")
    #
    #     return super(ProjectTask, self).write(vals)



# Check if the state restrictions
#     @api.model
#     def write(self, vals):
#         if 'state' in vals:
#             restricted_states = ['1_done', '1_canceled']
#
#             # Get the project manager of the task's project and current user
#             project_manager = self.project_id.user_id
#             current_user = self.env.user
#
#             # Check if the current user is the project manager
#             if current_user != project_manager:
#                 new_state = vals['state']
#                 if new_state in restricted_states:
#                     raise exceptions.UserError("Only the project manager can change the state of this task.")
#
#         return super(ProjectTask, self).write(vals)


    @api.model
    def write(self, vals):
        if 'state' in vals:
            restricted_states = ['1_done', '1_canceled']
            new_state = vals['state']
            # Get the project manager of the task's project and current user
            project_manager = self.project_id.user_id
            current_user = self.env.user


            # admin_group = self.env.ref('base.group_system')  # Reference to the Administrator group
            # _logger.info(f'admin group {admin_group}')
            #
            # admin_users = self.env['res.users'].search([('groups_id', 'in', admin_group.id)])
            # _logger.info(f'admin user {admin_users}')

            is_admin = current_user.has_group('base.group_system')
            _logger.info(f"Is Admin: {is_admin}")

            # Check if the current user is not admin and it also not project manager
            if not is_admin and current_user != project_manager:
                if new_state in restricted_states:
                    raise exceptions.UserError("Only the project manager and Administrator can change the state of this task.")

        return super(ProjectTask, self).write(vals)

