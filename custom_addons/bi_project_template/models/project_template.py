# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz
from datetime import datetime, timedelta
from odoo.fields import Datetime
import time
import logging

_logger = logging.getLogger(__name__)


class project_project(models.Model):
    _inherit = "project.project"

    x_template = fields.Char(string='Template')

    def write(self, vals):
        res = super().write(vals)
        if 'date_start' in vals:
            for project in self:
                last_task = self.env['project.task'].search([
                    ('project_id', '=', project.id)
                ], order='sequence desc', limit=1)

                if last_task and last_task.allocated_days_template > 0:
                    project.date = project.date_start + timedelta(days=last_task.allocated_days_template)
                else:
                    project.date = False
        return res

    @api.model
    def default_get(self, fields):
        stage_type_obj = self.env['template.task']
        state_new_id = stage_type_obj.search([('name', '=', 'New')], limit=1)
        if state_new_id:
            state_new_id.write({'sequence': 1, 'task_check': True})
        else:
            state_new_id = stage_type_obj.create({'name': 'New', 'sequence': 1, 'task_check': True})
        state_in_progress_id = stage_type_obj.search([('name', '=', 'In Progress')], limit=1)
        if state_in_progress_id:
            state_in_progress_id.write({'sequence': 2, 'task_check': True})
        else:
            progress_id = stage_type_obj.create({'name': 'In Progress', 'sequence': 2, 'task_check': True})
        state_cancel_id = stage_type_obj.search([('name', '=', 'Canceled')], limit=1)
        if state_cancel_id:
            state_cancel_id.write({'sequence': 3, 'task_check': True})
        else:
            cancel_id = stage_type_obj.create({'name': 'Canceled', 'sequence': 3, 'task_check': True})
        state_pending_id = stage_type_obj.search([('name', '=', 'Pending')], limit=1)
        if state_pending_id:
            state_pending_id.write({'sequence': 4, 'task_check': True})
        else:
            pending_id = stage_type_obj.create({'name': 'Pending', 'sequence': 4, 'task_check': True})
        state_closed_id = stage_type_obj.search([('name', '=', 'Closed')], limit=1)
        if state_closed_id:
            state_closed_id.write({'sequence': 5, 'task_check': True})
        else:
            closed_id = stage_type_obj.create({'name': 'Closed', 'sequence': 4, 'task_check': True})
        stage_list = []
        result = super(project_project, self).default_get(fields)
        for i in state_new_id:
            result['template_task_id'] = i.id
        return result

    def count_sequence(self):
        for a in self:
            stage_type_obj = a.env['template.task']
            state_in_progress_id = stage_type_obj.search([('name', '=', 'In Progress')], limit=1)
            state_template_id = stage_type_obj.search([('name', '=', 'Template')], limit=1)
            state_new_id = stage_type_obj.search([('name', '=', 'New')], limit=1)
            if a.template_task_id.id == int(state_new_id):
                a.sequence_state = 1
            elif a.template_task_id.id == int(state_in_progress_id):
                a.sequence_state = 2
            else:
                a.sequence_state = 3

    def set_template(self):
        for i in self:
            stage_type_obj = self.env['template.task']
            state_template_id = stage_type_obj.search([('name', '=', 'Template')], limit=1)
            state_new_id = stage_type_obj.search([('name', '=', 'New')], limit=1)
            if state_template_id:
                state_template_id.write({'sequence': 1, 'task_check': True})
                state_new_id.update({'sequence': 2, 'task_check': True})
                i.update({'template_task_id': state_template_id.id, 'sequence_state': 3, 'is_project_template': True})
            else:
                template_id = stage_type_obj.create({'name': 'Template', 'sequence': 1, 'task_check': True})
                template_id.write({'sequence': 1, 'task_check': True})
                state_new_id.write({'sequence': 2, 'task_check': True})
                i.write({'template_task_id': template_id.id, 'sequence_state': 3, 'is_project_template': True})
            state_template_id.write({'task_check': False})

    def action_open_project_title_wizard(self):
        return {
            'name': 'Enter Project Title',
            'type': 'ir.actions.act_window',
            'res_model': 'project.title.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id}
        }

    def copy(self, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        project = super(project_project, self).copy(default)
        stage_type_obj = self.env['template.task']
        state_new_id = stage_type_obj.search([('name', '=', 'New')], limit=1)
        if self.env.user.has_group('project.group_project_stages'):
            if self.env.context.get('default_is_project_template', True) and not self.env.context.get(
                    'project_template'):
                project.update({'template_task_id': state_new_id, 'sequence_state': 1, 'is_project_template': False})
        return project

    def reset_project(self):
        for i in self:
            stage_type_obj = self.env['project.task.type']
            state_new_id = stage_type_obj.search([('name', '=', 'New')], limit=1)
            if state_new_id:
                i.write({'template_task_id': state_new_id.id, 'sequence_state': 1})
            return

    def set_progress(self):
        for i in self:
            stage_type_obj = self.env['template.task']
            state_progress_id = stage_type_obj.search([('name', '=', 'In Progress')], limit=1)
            if state_progress_id:
                i.write({'template_task_id': state_progress_id.id, 'sequence_state': 2})
            return

    template_task_id = fields.Many2one('template.task', string="state")
    sequence_state = fields.Integer(compute="count_sequence", string="State Check")
    is_project_template = fields.Boolean('Is Project Template')

    project_template_form = fields.Many2one(
        'project.project',
        string="Project Template ",
        domain=[('is_project_template', '=', True)]
    )

    @api.model
    def create(self, vals):
        if self.env.context.get('import_file'):
            return self._create_from_import(vals)
        else:
            return self._create_from_ui(vals)

    def _create_from_import(self, vals):
        # Your existing logic from the automation action goes here,
        # adapted for `self.env` and `vals` instead of global env.
        template_project = self.browse(vals['project_template_form'])
        if 'project_template_form' in vals and vals['project_template_form']:
            vals['x_template'] = template_project.name

        new_project = super(project_project, self).create(vals)  # Create base project first to get ID
        new_project_id = new_project.id

        if template_project:
            project_template = self.env['project.project'].search([('name', '=', template_project.name)], limit=1)
            if project_template:
                template_stage_names = [stage.name for stage in project_template.type_ids]
                existing_stages = self.env['project.task.type'].search([('name', 'in', template_stage_names)])
                existing_stage_names = [stage.name for stage in existing_stages]

                new_stages = []
                for stage_template in project_template.type_ids:
                    if stage_template.name not in existing_stage_names:
                        new_stages.append({
                            'name': stage_template.name,
                            'project_ids': [(4, new_project_id)],
                            'sequence': stage_template.sequence,
                        })
                if new_stages:
                    self.env['project.task.type'].create(new_stages)

                all_stages = self.env['project.task.type'].search([('name', 'in', template_stage_names)])
                stage_map = {stage.name: stage.id for stage in all_stages}

                new_tasks = []
                task_map = {}

                for task_template in project_template.tasks:
                    new_task_vals = {
                        'name': task_template.name,
                        'project_id': new_project_id,
                        'sequence': task_template.sequence,
                        'stage_id': stage_map.get(task_template.stage_id.name, False),
                        'user_ids': [(6, 0, task_template.user_ids.ids)],
                        'tag_ids': [(6, 0, task_template.tag_ids.ids)],  # corrected many2many field format
                    }
                    new_tasks.append(new_task_vals)

                if new_tasks:
                    tasks = self.env['project.task'].create(new_tasks)
                    for task_template, new_task in zip(project_template.tasks, tasks):
                        task_map[task_template.id] = new_task

                    task_dependencies = []
                    for task_template in project_template.tasks:
                        depend_on_ids = [
                            task_map[temp_dependency.id].id for temp_dependency in task_template.depend_on_ids
                            if temp_dependency.id in task_map
                        ]
                        if depend_on_ids:
                            task_dependencies.append((task_map[task_template.id].id, depend_on_ids))

                    for task_id, depend_on_ids in task_dependencies:
                        self.env['project.task'].browse(task_id).write({'depend_on_ids': [(6, 0, depend_on_ids)]})

        return new_project

    def _create_from_ui(self, vals):
        if self.env.context.get('skip_template_copy'):
            return super(project_project, self).create(vals)

        if vals.get('project_template_form'):
            template_project = self.browse(vals['project_template_form'])

            if template_project:
                date_start = fields.Datetime.to_datetime(vals.get('date_start')) or datetime.now()

                # Copy the template with updated name and remove template flag
                new_project = template_project.with_context(skip_template_copy=True,
                                                            mail_create_nolog=True,
                                                            mail_notrack=True).copy({
                    'name': vals.get('name', template_project.name),
                    'is_project_template': False,
                    'project_template_form': template_project.id,
                    'date_start': date_start,
                    'user_id': vals.get('user_id', template_project.user_id.id),
                    'x_template': template_project.name
                })

                # Option 1: Batch update using ORM (safer but slower)
                # if new_project.task_ids:
                #     tasks_to_update = new_project.task_ids.filtered('allocated_days_template')
                #     if tasks_to_update:
                #         # Disable mail tracking and other overhead during batch update
                #         tasks_to_update.with_context(
                #             mail_notrack=True,
                #             tracking_disable=True
                #         ).write({})  # Empty write to batch process
                #
                #         # Update each task's deadline
                #         for task in tasks_to_update:
                #             task.with_context(mail_notrack=True).write({
                #                 'date_deadline': date_start + timedelta(days=task.allocated_days_template)
                #             })

                # Option 2: Raw SQL update (fastest but bypasses ORM validations)
                if new_project.task_ids:
                    self.env.cr.execute("""
                        UPDATE project_task t
                        SET date_deadline = p.date_start + (t.allocated_days_template || ' days')::interval
                        FROM project_project p
                        WHERE t.project_id = p.id
                          AND t.project_id = %s
                          AND t.allocated_days_template IS NOT NULL
                    """, (new_project.id,))

                return new_project

        # No template: fallback to regular create
        return super(project_project, self).create(vals)

    def action_view_tasks(self):
        # Check for custom context key to open form
        if self.env.context.get('open_project_form'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'project.project',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'current',
                'context': {},
            }
        # Otherwise, fallback to default behavior
        return super().action_view_tasks()
