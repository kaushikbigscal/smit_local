# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, api, fields
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def open_full_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task',
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def delete(self):
        """Delete the calendar event associated with this task"""
        self.ensure_one()
        # Find calendar events linked to this task
        calendar_events = self.env['calendar.event'].search([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', self.id)
        ])

        if calendar_events:
            calendar_events.with_context(no_mail_to_attendees=True).unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class CrmLead(models.Model):
    """Override CRM lead model for additional calendar event cleanup"""
    _inherit = 'crm.lead'

    def open_full_lead_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lead',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def delete(self):
        """Delete the calendar event associated with this lead"""
        self.ensure_one()
        # Find calendar events linked to this lead
        calendar_events = self.env['calendar.event'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', self.id)
        ])

        if calendar_events:
            calendar_events.with_context(no_mail_to_attendees=True).unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def write(self, vals):
        """Override write to clean up calendar events when lead type changes"""
        # Check if type is being changed from 'lead' to something else
        if vals.get('type') in ['opportunity', 'quotation'] and self.type == 'lead':
            # Find calendar events linked to this lead
            lead_events = self.env['calendar.event'].search([
                ('res_model', '=', 'crm.lead'),
                ('res_id', '=', self.id),
                ('calendar_rule_id', '!=', False)  # Only events created by calendar rules
            ])

            # Write the changes first
            result = super().write(vals)

            # After conversion, delete the lead events
            if lead_events:
                lead_events.with_context(no_mail_to_attendees=True).unlink()
                _logger.info(
                    f"Cleaned up {len(lead_events)} calendar events from lead {self.id} converted to {vals.get('type')}")

            return result

        return super().write(vals)


class FieldVisit(models.Model):
    _inherit = 'field.visit'

    def open_visit_full_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visit',
            'res_model': 'field.visit',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def delete(self):
        """Delete the calendar event associated with this task"""
        self.ensure_one()
        # Find calendar events linked to this task
        calendar_events = self.env['calendar.event'].search([
            ('res_model', '=', 'field.visit'),
            ('res_id', '=', self.id)
        ])

        if calendar_events:
            calendar_events.with_context(no_mail_to_attendees=True).unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
