import logging

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError, AccessError
import random
from functools import lru_cache
from odoo.osv.expression import expression
from odoo.tools import ormcache

_logger = logging.getLogger(__name__)


class CalendarRule(models.Model):
    _name = 'calendar.rule'
    _description = 'Calendar Rule'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color', default=lambda self: random.randint(1, 11))

    model_id = fields.Many2one('ir.model', required=True, string="Model", ondelete='cascade')
    model_name = fields.Char(related='model_id.model', readonly=True, store=True)

    # Field mappings with proper domains
    name_field_id = fields.Many2one(
        'ir.model.fields',
        string="Event Name Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'text'])]"
    )
    start_date_field_id = fields.Many2one(
        'ir.model.fields',
        string="Start Date Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['datetime', 'date'])]"
    )
    stop_date_field_id = fields.Many2one(
        'ir.model.fields',
        string="Stop Date Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['datetime', 'date'])]"
    )
    attendee_field_id = fields.Many2one(
        'ir.model.fields',
        string="Attendees Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['many2one', 'many2many']), ('relation', '=', 'res.partner')]"
    )
    description_field_id = fields.Many2one(
        'ir.model.fields',
        string="Description Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'text', 'html'])]"
    )
    company_field_id = fields.Many2one(
        'ir.model.fields',
        string="Company Field",
        ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one'), ('relation', '=', 'res.company')]"
    )

    domain = fields.Char(
        string="Domain",
        help="Optional domain to filter records (Python expression)",
        default="[]"
    )

    automation_id = fields.Many2one(
        'base.automation', string="Automation Rule", ondelete='set null'
    )

    form_view_id = fields.Many2one(
        'ir.ui.view',
        string='Form View to open',
        domain="[('type', '=', 'form'), ('model', '=', model_name)]",
    )

    # Statistics
    event_count = fields.Integer(string="Events Count", compute='_compute_event_count')
    last_sync = fields.Datetime(string="Last Sync", readonly=True)

    logo = fields.Binary("Logo", attachment=True)  # store in filestore
    # logo_mimetype = fields.Char("Logo MIME")  # optional (if you used for other things)
    logo_url = fields.Char("Logo URL", compute='_compute_logo_url', store=False)

    @api.depends('logo')
    def _compute_logo_url(self):
        for rec in self:
            if rec.logo:
                # relative path — Odoo will resolve correctly in the browser
                rec.logo_url = f'/web/image?model=calendar.rule&id={rec.id}&field=logo'
            else:
                rec.logo_url = False

    @api.model
    @ormcache('self.env.uid')
    def get_available_rules(self):
        """Return only rules for which the current user has create rights (ACL + Record Rules)."""
        rules = self.search([("active", "=", True)])
        if not rules:
            return []

        allowed = []
        rules_by_model = {}

        # group rules by model_name
        for rule in rules:
            rules_by_model.setdefault(rule.model_name, []).append(rule)

        for model_name, model_rules in rules_by_model.items():
            Model = self.env[model_name].with_user(self.env.user)

            try:
                # 1. First check ACLs
                Model.check_access_rights("create", raise_exception=True)
                print("1", Model.check_access_rights("create", raise_exception=True))

                # 2. Then check record rules
                # Odoo 17 requires calling check_access_rule, not _check_record_rules
                Model.check_access_rule("create")
                print("2", Model.check_access_rule("create"))

            except AccessError:
                continue  # skip all rules of this model
            print("Model", model_name)
            print("model_rules", model_rules)

            for rule in model_rules:
                allowed.append({
                    "id": rule.id,
                    "name": rule.name,
                    "logo_url": rule.logo_url,
                    "model_name": rule.model_name,
                    # "description": getattr(rule.description_field_id, "field_description", ""),
                })

        return allowed

    def action_open_target_model_form(self):
        """Open a creation form for the model configured on this rule."""
        self.ensure_one()
        model_name = self.model_name
        if not model_name:
            return {'type': 'ir.actions.act_window_close'}

        # Get the calendar context (start/stop times) if available
        context = dict(self.env.context)

        # If we have calendar context, pass the datetime info
        calendar_start = context.get('default_start')
        calendar_stop = context.get('default_stop')

        # Add calendar rule context
        context.update({
            'default_from_calendar_rule_id': self.id,
            'calendar_rule_id': self.id,
        })

        if model_name == 'crm.lead' and self.domain:
            domain = safe_eval(self.domain)
            for cond in domain:
                if isinstance(cond, (list, tuple)) and len(cond) >= 3:
                    field, op, value = cond[0], cond[1], cond[2]
                    if field == "type" and op in ("=", "=="):
                        context['default_type'] = value

        if model_name == 'project.task' and self.domain:
            domain = safe_eval(self.domain)
            for cond in domain:
                if isinstance(cond, (list, tuple)) and len(cond) >= 3:
                    field, op, value = cond[0], cond[1], cond[2]
                    if field == "is_fsm" and op in ("=", "=="):
                        if value:
                            context['default_is_fsm'] = True

                            # find first FSM project (you can refine domain if needed)
                            fsm_project = self.env['project.project'].search(
                                [('is_fsm', '=', True)], limit=1
                            )
                            if fsm_project:
                                context['default_project_id'] = fsm_project.id

                        else:

                            context['default_is_fsm'] = False

                            # default to a normal project
                            normal_project = self.env['project.project'].search(
                                [('is_fsm', '=', False)], limit=1
                            )
                            if normal_project:
                                context['default_project_id'] = normal_project.id

        # If the target model has date fields mapped in the rule, set them
        if calendar_start and self.start_date_field_id:
            context[f'default_{self.start_date_field_id.name}'] = calendar_start
        if calendar_stop and self.stop_date_field_id:
            context[f'default_{self.stop_date_field_id.name}'] = calendar_stop

        # Special handling for project.task to use appropriate form view
        views = [(False, 'form')]
        if model_name == 'project.task':
            print("Yes Yes")
            print("Rule name:", self.name)
            print("Form view ID:", self.form_view_id.id if self.form_view_id else "None")

            # Check if this is a todo rule (by name or form_view_id)
            is_todo_rule = (
                    'todo' in self.name.lower() or
                    (self.form_view_id and 'todo' in self.form_view_id.name.lower())
            )

            if is_todo_rule:
                print("This is a TODO rule - using project todo view")
                # Add project todo specific context
                context.update({
                    'search_default_open_tasks': 1,
                    'tree_view_ref': 'project_todo.project_task_view_todo_tree'
                })
                print("Updated context for TODO")
                print("Context", context)

                # Try to get the project todo view
                try:
                    todo_view = self.env.ref('project_todo.project_task_view_todo_form', raise_if_not_found=False)
                    if todo_view:
                        print("Found project todo view")
                        views = [(todo_view.id, 'form')]
                        print("todo view id", views)
                except Exception as e:
                    print("Error getting project todo view:", e)
                    # Fallback to default form view if project todo view not found
                    pass
            else:
                print("This is a TASK rule - using default task form")
                # Use default project task form view
                try:
                    task_view = self.env.ref('project.view_task_form2', raise_if_not_found=False)
                    if task_view:
                        print("Found default task view")
                        views = [(task_view.id, 'form')]
                        print("task view id", views)
                except Exception as e:
                    print("Error getting default task view:", e)
                    pass

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create: %s') % (self.name or model_name),
            'res_model': model_name,
            'view_mode': 'form',
            'views': views,
            'target': 'new',
            'context': context,
        }

    @api.model
    def _sync_from_automation(self, model_name, record_id):
        record = self.env[model_name].browse(record_id)
        if not record.exists():
            return

        # Fetch only rules for the exact model
        rules = self.search([
            ('model_name', '=', model_name),
            ('active', '=', True)
        ])

        for rule in rules:
            try:
                # Only process if the record matches the domain
                domain = safe_eval(rule.domain or '[]', {'uid': self.env.uid})
                if not record.filtered_domain(domain):
                    continue

                # Prepare vals for this record only
                vals = rule._prepare_calendar_event_vals(record)
                if not vals:
                    continue

                vals.update({
                    'res_model': model_name,
                    'res_id': record.id,
                    'calendar_rule_id': rule.id,
                })

                # Update/create only for this record
                existing = self.env['calendar.event'].search([
                    ('res_model', '=', model_name),
                    ('res_id', '=', record.id),
                    ('calendar_rule_id', '=', rule.id),
                ], limit=1)

                if existing:
                    existing.write(vals)
                else:
                    self.env['calendar.event'].create(vals)

            except Exception as e:
                _logger.warning(
                    f"Calendar sync error for {model_name}({record_id}) with rule {rule.id}: {e}"
                )

    @api.model
    def create(self, vals):
        rule = super().create(vals)
        # Generate automation rule after creation
        if rule.model_id:
            rule._generate_automation_rule()
        return rule

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals and vals['active'] is False:
            for rule in self:
                if rule.automation_id:
                    rule.automation_id.active = False
        return res

    def _generate_automation_rule(self):
        Automation = self.env['base.automation'].sudo()
        IrModel = self.env['ir.model'].sudo()

        for rule in self:
            model = IrModel.search([('model', '=', rule.model_name)], limit=1)
            if not model:
                continue
            filter_domain = rule.domain or "[]"
            automation_vals = {
                'name': f'Sync Calendar from {rule.model_name}',
                'model_id': model.id,
                'model_name': rule.model_name,
                'trigger': 'on_create_or_write',
                'filter_domain': filter_domain,  # Apply on all records; customize if needed
                'active': rule.active,
                'action_server_ids': [(0, 0, {
                    'name': f'Execute Calendar Sync: {rule.model_name}',
                    'state': 'code',
                    'model_id': model.id,
                    'code': f"env['calendar.rule']._sync_from_automation('{rule.model_name}', record.id)",
                })]
            }

            if rule.automation_id and rule.automation_id.exists():
                rule.automation_id.sudo().write(automation_vals)
            else:
                automation = Automation.create(automation_vals)
                self.env.cr.execute(
                    "UPDATE calendar_rule SET automation_id = %s WHERE id = %s",
                    (automation.id, rule.id)
                )
                rule.invalidate_recordset(['automation_id'])

    def unlink(self):
        # Store automation IDs before deletion to avoid recordset issues
        automation_ids = []
        for rule in self:
            try:
                # Check if automation_id exists and has a valid ID
                if rule.automation_id and hasattr(rule.automation_id, 'id') and rule.automation_id.id:
                    # Double check the record exists in database
                    if rule.automation_id.exists():
                        automation_ids.append(rule.automation_id.id)
            except Exception as e:
                _logger.warning("Error accessing automation_id for rule %s: %s", rule.id, e)
                # Try to get the ID directly from database
                try:
                    self.env.cr.execute(
                        "SELECT automation_id FROM calendar_rule WHERE id = %s AND automation_id IS NOT NULL",
                        (rule.id,)
                    )
                    result = self.env.cr.fetchone()
                    if result and result[0]:
                        automation_ids.append(result[0])
                except Exception as db_e:
                    _logger.warning("Error getting automation_id from database for rule %s: %s", rule.id, db_e)

        # Delete the calendar rule records first
        result = super().unlink()

        # Then try to delete the automation rules
        if automation_ids:
            Automation = self.env['base.automation'].sudo()
            try:
                # Search for existing automation records by ID
                automations = Automation.browse(automation_ids).exists()
                if automations:
                    automations.unlink()
            except Exception as e:
                _logger.warning("Failed to unlink automations %s: %s", automation_ids, e)

        return result

    @api.depends('model_id')
    def _compute_event_count(self):
        for rule in self:
            if rule.model_id:
                count = self.env['calendar.event'].search_count([
                    ('res_model', '=', rule.model_id.model),
                    ('calendar_rule_id', '=', rule.id)
                ])
                rule.event_count = count
            else:
                rule.event_count = 0

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Clear field mappings when model changes"""
        if self.model_id:
            self.name_field_id = False
            self.start_date_field_id = False
            self.stop_date_field_id = False
            self.attendee_field_id = False
            self.description_field_id = False
            self.company_field_id = False
            self.domain = "[]"

    @api.constrains('domain')
    def _check_domain(self):
        """Validate domain syntax"""
        for rule in self:
            if rule.domain:
                try:
                    safe_eval(rule.domain or '[]', {'uid': self.env.uid})
                except Exception as e:
                    raise ValidationError(_('Invalid domain syntax: %s') % str(e))

    @api.constrains('start_date_field_id')
    def _check_start_date_field(self):
        """Ensure start date field is selected"""
        for rule in self:
            if not rule.start_date_field_id:
                raise ValidationError(_('Start Date Field is required'))

    def action_sync_existing_records(self):
        """Sync existing records to calendar events"""
        self.ensure_one()

        if not self.start_date_field_id:
            raise ValidationError(_('Start Date Field must be configured before syncing'))

        CalendarEvent = self.env['calendar.event']
        Model = self.env[self.model_id.model]

        # Parse domain safely
        try:
            domain = safe_eval(self.domain or '[]', {'uid': self.env.uid})
        except Exception as e:
            raise ValidationError(_('Invalid domain: %s') % str(e))

        # Get records to sync
        records = Model.search(domain)
        total_created = 0
        total_updated = 0

        for rec in records:
            # Check if calendar event already exists
            existing = CalendarEvent.search([
                ('res_model', '=', self.model_id.model),
                ('res_id', '=', rec.id),
                ('calendar_rule_id', '=', self.id)
            ])

            # Prepare event values
            vals = self._prepare_calendar_event_vals(rec)
            if not vals:
                continue  # Skip if no valid values

            if existing:
                # Update existing event
                existing.write(vals)
                total_updated += 1
            else:
                # Create new event
                vals.update({
                    'res_model': self.model_id.model,
                    'res_id': rec.id,
                    'calendar_rule_id': self.id,
                })
                CalendarEvent.create(vals)
                total_created += 1

        # Update last sync time using SQL to avoid write() recursion
        self.env.cr.execute(
            "UPDATE calendar_rule SET last_sync = %s WHERE id = %s",
            (fields.Datetime.now(), self.id)
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Calendar Sync Complete'),
                'message': _('%d events created, %d events updated.') % (total_created, total_updated),
                'type': 'success',
                'sticky': False,
            }
        }

    def _prepare_calendar_event_vals(self, record):
        """Prepare calendar event values from record"""
        self.ensure_one()
        vals = {}

        # Event name
        if self.name_field_id:
            vals['name'] = getattr(record, self.name_field_id.name, '') or record.display_name
        else:
            vals['name'] = record.display_name

        # Get start/stop values from record
        start_value = getattr(record, self.start_date_field_id.name, False) if self.start_date_field_id else False
        stop_value = getattr(record, self.stop_date_field_id.name, False) if self.stop_date_field_id else False

        if start_value and stop_value:
            # Both dates present → normal event
            vals['start'] = start_value
            vals['stop'] = stop_value
        else:
            # Missing either → full-day event
            vals['allday'] = True
            today = fields.Date.today()
            vals['start'] = today
            vals['stop'] = today  # Calendar full-day events in Odoo can have same start/stop for single-day

        # Description
        if self.description_field_id:
            desc_value = getattr(record, self.description_field_id.name, '')
            vals['description'] = desc_value or ''

        # Attendees
        if self.attendee_field_id:
            attendee_value = getattr(record, self.attendee_field_id.name, False)
            if attendee_value:
                if self.attendee_field_id.ttype == 'many2one':
                    vals['partner_ids'] = [(4, attendee_value.id)]
                elif self.attendee_field_id.ttype == 'many2many':
                    vals['partner_ids'] = [(6, 0, attendee_value.ids)]

        # Company
        if self.company_field_id:
            company_value = getattr(record, self.company_field_id.name, False)
            if company_value:
                vals['company_id'] = company_value.id

        return vals

    def action_view_events(self):
        """View calendar events created by this rule"""
        self.ensure_one()
        return {
            'name': _('Events from %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'tree,form,calendar',
            'domain': [
                ('res_model', '=', self.model_id.model),
                ('calendar_rule_id', '=', self.id)
            ],
            'context': {'default_calendar_rule_id': self.id}
        }

    def action_delete_events(self):
        """Delete all events created by this rule"""
        self.ensure_one()
        events = self.env['calendar.event'].search([
            ('res_model', '=', self.model_id.model),
            ('calendar_rule_id', '=', self.id)
        ])
        event_count = len(events)
        events.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Events Deleted'),
                'message': _('%d events deleted.') % event_count,
                'type': 'info',
            }
        }
