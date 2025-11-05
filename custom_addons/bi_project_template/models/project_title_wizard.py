from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from odoo.fields import Datetime

class ProjectTitleWizard(models.TransientModel):
    _name = 'project.title.wizard'
    _description = 'Enter Project Title'

    project_name = fields.Char(string="Project Name", required=True)

    def create_project(self):

        if self.env.context.get('skip_template_copy'):
            return super(ProjectTemplateWizard, self).create(self)

        active_id = self.env.context.get('active_id')
        template_project = self.env['project.project'].browse(active_id)
        date_start = Datetime.now()
        # Create a new project with the name from the wizard and set is_project_template to False
        new_project = template_project.with_context(skip_template_copy=True).copy({
            'name': self.project_name,
            'is_project_template': False,  # Ensure this is set to False
            'project_template_form': template_project.id,
            'date_start': date_start,
        }, context={'default_is_project_template': False})  # Set context to prevent copy method from overriding

        for task in new_project.task_ids:
            if task.allocated_days_template:
                task.date_deadline = date_start + timedelta(days=task.allocated_days_template)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': new_project.id,
            'view_mode': 'form',
            'target': 'current',
        }
 