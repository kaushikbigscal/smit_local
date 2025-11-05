from odoo import models, api, fields
from datetime import datetime


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    event_origin = fields.Selection([
        ('task', 'Task'),
        ('lead', 'Lead'),
        ('other', 'Other')
    ], string='Event Source', default='other', tracking=True)
    @api.model
    def retrieve_dashboard(self):
        """Retrieve dynamic calendar dashboard based on installed modules"""
        registry = self.env.registry
        result = {}
        module_data = {}

        # Base: always available
        result['total_events'] = self.env['calendar.event'].search_count([])

        # Calendar Events tagged as Meetings (if you’re tagging)
        result['meeting_count'] = self.env['calendar.event'].search_count([])

        # Conditional checks
        if 'crm.lead' in registry.models:
            Lead = self.env['crm.lead']
            result['lead_count'] = Lead.search_count([])
            module_data['crm'] = True
            # For "Calls", fallback safe search (optional if you log them via activities)
            try:
                Activity = self.env['mail.activity']
                call_count = Activity.search_count([('activity_type_id.name', 'ilike', 'call')])
                result['call_count'] = call_count
            except Exception:
                result['call_count'] = 0
        else:
            module_data['crm'] = False

        if 'project.project' in registry.models and 'project.task' in registry.models:
            Project = self.env['project.project']
            Task = self.env['project.task']
            result['project_count'] = Project.search_count([])
            result['task_count'] = Task.search_count([])
            module_data['project'] = True
        else:
            module_data['project'] = False

        result['module_info'] = module_data
        return result
