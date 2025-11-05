from odoo import models, fields, api, SUPERUSER_ID
from odoo.tools.safe_eval import safe_eval


class CalendarRule(models.Model):
    _name = 'calendar.rule'
    _description = 'Calendar Rule'

    name = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', required=True, string="Model", ondelete='cascade')

    name_field_id = fields.Many2one('ir.model.fields', string="Event Name Field", ondelete='set null')
    start_date_field_id = fields.Many2one('ir.model.fields', string="Start Date Field", ondelete='set null')
    stop_date_field_id = fields.Many2one('ir.model.fields', string="Stop Date Field", ondelete='set null')
    attendee_field_id = fields.Many2one('ir.model.fields', string="Attendees Field", ondelete='set null')
    description_field_id = fields.Many2one('ir.model.fields', string="Description Field", ondelete='set null')
    company_field_id = fields.Many2one('ir.model.fields', string="Company Field", ondelete='set null')

    domain = fields.Char(string="Domain", help="Optional domain to filter records")

        # @api.model
        # def get_calendar_events(self):
        #     events = []
        #     rules = self.search([])
        #
        #     for rule in rules:
        #         Model = self.env[rule.model_id.model]
        #         domain = safe_eval(rule.domain or '[]', {'uid': self.env.uid})
        #
        #         for rec in Model.search(domain):
        #             try:
        #                 events.append({
        #                     'title': getattr(rec, rule.name_field_id.name, '') or '',
        #                     'start': getattr(rec, rule.start_date_field_id.name, False),
        #                     'end': getattr(rec, rule.stop_date_field_id.name, False),
        #                     'attendees': getattr(rec, rule.attendee_field_id.name, False),
        #                     'description': getattr(rec, rule.description_field_id.name, ''),
        #                     'company_id': getattr(rec, rule.company_field_id.name, False),
        #                     'res_model': rule.model_id.model,
        #                     'res_id': rec.id,
        #                 })
        #             except AttributeError:
        #                 continue
        #
        #     return events

    def action_sync_existing_records(self):
        CalendarEvent = self.env['calendar.event']
        total_created = 0

        for rule in self:
            Model = self.env[rule.model_id.model]
            domain = safe_eval(rule.domain or '[]', {'uid': self.env.uid})
            for rec in Model.search(domain):
                existing = CalendarEvent.search([
                    ('res_model', '=', rule.model_id.model),
                    ('res_id', '=', rec.id)
                ])
                if not existing and hasattr(rec, '_prepare_calendar_event_from_rule'):
                    vals = rec._prepare_calendar_event_from_rule(rule)
                    CalendarEvent.create(vals)
                    total_created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Calendar Sync',
                'message': f'{total_created} events synced.',
                'type': 'success',
            }
        }




