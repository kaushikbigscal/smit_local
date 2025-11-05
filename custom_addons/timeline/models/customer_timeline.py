# -*- coding: utf-8 -*-
from odoo import api, fields, models
from collections import defaultdict
from datetime import datetime, timedelta
from odoo.tools import format_time
import json
import logging

_logger = logging.getLogger(__name__)


class CustomerTimeline(models.TransientModel):
    _name = "customer.timeline"
    _description = "Customer Timeline Dashboard"

    date_from = fields.Date(string="Date", default=lambda self: fields.Date.today() - timedelta(days=30), required=True)
    date_to = fields.Date(string="To Date", default=fields.Date.today, required=True)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, domain=lambda self: self._get_partner_domain())
    selected_model_ids = fields.Many2many('ir.model', string="Selected Models", help="Models to display in timeline", default=lambda self: self._get_default_models())
    unified_timeline_display = fields.Html(string="Timeline Display", compute="_compute_unified_timeline", sanitize=False)
    activity_summary = fields.Html(string="Summary", compute="_compute_timeline")
    active_model = fields.Char(string="Active Model")
    is_loaded = fields.Boolean(string="Is Loaded", default=False)
    active_filter = fields.Char(string="Active Filter", default="all")
    name = fields.Char(compute="_compute_name")

    @api.depends("partner_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.partner_id.name or 'Customer'}'s Timeline"

    @api.model
    def _get_partner_domain(self):
        employee = self.env.user.employee_id
        domain = []
        if not employee:
            return domain

        # Get the current company from context or user
        current_company = self.env.company

        if employee.customer_access_scope == 'all':
            domain = [
                ('parent_id', '=', False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                ('employee_ids', '=', False),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]

        elif employee.customer_access_scope == 'self':
            domain = [
                ('customer_visibility_access', '=', employee.id),
                ('parent_id', '=', False),
                ("employee_ids", "=", False),
                ('company_type', '!=', 'distribution'),
                ('company_id', 'in', [False, current_company.id]),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'assigned':
            assignment_lines = self.env['customer.assignment.line'].search([
                ('assignee_name', '=', employee.id),
                ('company_id', '=', current_company.id)
            ])
            assigned_customers = assignment_lines.mapped('client_id')
            domain = [
                ('id', 'in', assigned_customers.ids),
                ('parent_id', '=', False),
                ("employee_ids", "=", False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'select':
            select_domain = []
            # Use the employee's company or current company
            company = employee.company_id or current_company

            if employee.restrict_by_location:
                # ZONE/SUB-ZONE FILTERING - SIMPLIFIED
                if company.restrict_zone and employee.location_restriction_zone:
                    zone_filter_ids = []

                    # FIRST: Check if sub-zones are selected
                    if employee.allowed_sub_zone_ids:
                        zone_filter_ids = employee.allowed_sub_zone_ids.ids
                    # SECOND: If no sub-zones selected, check main zones
                    elif employee.allowed_zone_ids:
                        # Get all sub-zones under the selected main zones
                        sub_zones_from_zones = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ])
                        zone_filter_ids = sub_zones_from_zones.ids

                    # Apply the filter if we have any zone IDs
                    if zone_filter_ids:
                        select_domain.append(('zone_id', 'in', zone_filter_ids))
                if company.restrict_state and employee.location_restriction_state and employee.allowed_state_ids:
                    select_domain.append(('state_id', 'in', employee.allowed_state_ids.ids))
                if company.restrict_city and employee.location_restriction_city and employee.allowed_city_ids:
                    if 'city_id' in self.env['res.partner']._fields:
                        select_domain.append(('city_id', 'in', employee.allowed_city_ids.ids))
                    else:
                        select_domain.append(('city', 'in', employee.allowed_city_ids.mapped('name')))

            if employee.restrict_by:
                if company.restrict_customer_class and employee.customer_class and employee.allowed_customer_class_ids:
                    select_domain.append(('customer_class_id', 'in', employee.allowed_customer_class_ids.ids))
                if company.restrict_product_brand and employee.product_brand and employee.allowed_product_brand_ids:
                    select_domain.append(('brand_id', 'in', employee.allowed_product_brand_ids.ids))

            # Final domain with company restriction
            if select_domain:
                select_domain.append(('parent_id', '=', False))
                select_domain.append(('company_id', 'in', [False, current_company.id]))
                domain = select_domain
            elif employee.allowed_customer_ids:
                domain = [
                    ('id', 'in', employee.allowed_customer_ids.ids),
                    ('parent_id', '=', False),
                    ("employee_ids", "=", False),
                    ('company_id', 'in', [False, current_company.id]),
                    ('company_type', '!=', 'distribution'),
                    '|',
                    ('user_ids', '=', False),
                    ('user_ids.share', '=', True),
                ]
            else:
                domain = [('id', '=', False)]  # No access if no restrictions defined

        # Add company filter to ensure multi-company safety
        if not any(term[0] == 'company_id' for term in domain):
            domain.append(('company_id', 'in', [False, current_company.id]))

        return domain

    def action_load_timeline(self):
        """Create/update record with is_loaded=True and return view action"""
        self.write({'is_loaded': True, 'active_filter': 'all'})
        return {
            "type": "ir.actions.act_window_close",
        }

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Reset loaded flag when partner changes"""
        self.is_loaded = False

    @api.model
    def get_current_timeline_model(self):
        """Return the current model name"""
        return self._name

    @api.model
    def create(self, vals):
        if 'active_filter' not in vals:
            vals['active_filter'] = 'all'
        return super().create(vals)

    def _get_default_models(self):
        """Get default models from settings"""
        setting = self.env['ir.config_parameter'].sudo()
        model_ids = setting.get_param("timeline.customer_timeline_model_ids", "[]")
        try:
            model_ids = json.loads(model_ids) if model_ids else []
            return [(6, 0, model_ids)] if model_ids else []
        except Exception:
            return []

    @api.depends('partner_id', 'date_from', 'date_to', 'selected_model_ids')
    def _compute_unified_timeline(self):
        """Compute unified display with buttons and timeline together"""
        for rec in self:
            if not rec.partner_id or not rec.date_from or not rec.date_to:
                rec.unified_timeline_display = rec._get_empty_state_with_buttons()
                continue
            rec.unified_timeline_display = rec._generate_unified_html()

    def _generate_unified_html(self):
        """Generate unified HTML with action-based load workflow"""
        if not self.is_loaded:
            entity_name = 'Employee' if hasattr(self, 'employee_id') else 'Customer'
            entity_field = 'employee_id' if hasattr(self, 'employee_id') else 'partner_id'
            entity_value = getattr(self, entity_field, False)
            if not entity_value or not self.date_from or not self.date_to:
                return f"""
                <div class="unified_timeline_container">
                    <div class="timeline_content_section" style="text-align:center; padding:40px;">
                        <div style="margin-bottom: 20px;">
                            <i class="fa fa-info-circle" style="font-size: 24px; color: #f39c12; margin-bottom: 10px;"></i>
                        </div>
                        <h5 style="margin-bottom: 16px;">Setup Required</h5>
                        <p class="text-muted" style="margin-bottom:16px;">
                            Please select the {entity_name} and set the Date range above to continue.
                        </p>
                    </div>
                </div>
                """
            return f"""
            <div class="unified_timeline_container">
                <div class="timeline_content_section" style="text-align:center; padding:40px;">
                    <div style="margin-bottom: 20px;">
                        <i class="fa fa-calendar" style="font-size: 24px; color: #875A7B; margin-bottom: 10px;"></i>
                    </div>
                    <h5 style="margin-bottom: 16px;">Ready to Load Timeline</h5>
                    <p class="text-muted" style="margin-bottom:24px;">
                        {entity_name}: <strong>{entity_value.display_name}</strong><br/>
                        Date Range: <strong>{self.date_from.strftime('%B %d, %Y')} - {self.date_to.strftime('%B %d, %Y')}</strong>
                    </p>
                </div>
            </div>
            """
        if not self.active_filter:
            self.active_filter = 'all'
        filter_buttons_html = self._get_filter_buttons_html()
        try:
            mobile_visible_buttons_html, mobile_dropdown_buttons_html = self._get_split_filter_buttons_html()
        except:
            mobile_visible_buttons_html = filter_buttons_html
            mobile_dropdown_buttons_html = ""
        selected_models = []
        try:
            if self.selected_model_ids:
                selected_models = self.selected_model_ids.ids
        except (AttributeError, TypeError):
            selected_models = []
        if not selected_models:
            setting = self.env['ir.config_parameter'].sudo()
            model_param_key = "timeline.employee_timeline_model_ids" if hasattr(self, 'employee_id') else "timeline.customer_timeline_model_ids"
            model_ids_param = setting.get_param(model_param_key, "[]")
            try:
                selected_models = json.loads(model_ids_param) if model_ids_param else []
            except Exception as e:
                _logger.error("Timeline: Failed to parse model_ids: %s", e)
                selected_models = []
        if not selected_models:
            timeline_html = "<div class='alert alert-info mt-3'>No models configured or selected. Please configure models in General Settings > Timeline.</div>"
        else:
            timeline_dict, model_stats, won_lead_total, won_lead_count = self._generate_timeline_data(selected_models)
            timeline_html = self._generate_timeline_html_content(timeline_dict, model_stats, won_lead_total, won_lead_count)
        unified_html = f"""
        <div class="unified_timeline_container">
            <div class="filter_section">
                <!-- Desktop filter buttons (visible on desktop/tablet) -->
                <div class="desktop_filter_container">
                    <div class="filter_buttons_wrapper">
                        {filter_buttons_html}
                    </div>
                </div>
                <!-- Mobile filter layout (visible on mobile only) -->
                <div class="mobile_filter_container">
                    <div class="mobile_visible_buttons">
                        {mobile_visible_buttons_html}
                    </div>
                    {mobile_dropdown_buttons_html and f'''
                    <div class="mobile_more_dropdown">
                        <button class="mobile_more_btn" onclick="toggleMobileMoreDropdown()">
                            More Options
                        </button>
                        <div class="mobile_dropdown_content" id="mobileDropdownContent">
                            {mobile_dropdown_buttons_html}
                        </div>
                    </div>
                    ''' or ''}
                </div>
            </div>
            <div class="timeline_content_section" id="timeline_container" data-res-model="{self._name}" data-res-id="{self.id}" data-loaded="1">
                {timeline_html}
            </div>
        </div>
        """
        return unified_html

    @api.model
    def filter_timeline_data(self, filter_value):
        """Handle filter action from frontend with task/service call support"""
        if not self.env.context.get('active_id'):
            return {'error': 'No active timeline found'}
        timeline = self.browse(self.env.context['active_id'])
        if not timeline.exists():
            return {'error': 'Timeline not found'}
        timeline.write({'active_filter': filter_value})
        selected_models = []
        filter_domain = []
        if filter_value != 'all':
            if '_task' in str(filter_value):
                model_id = int(str(filter_value).replace('_task', ''))
                selected_models = [model_id]
                filter_domain = [('is_fsm', '=', False)]
            elif '_fsm' in str(filter_value):
                model_id = int(str(filter_value).replace('_fsm', ''))
                selected_models = [model_id]
                filter_domain = [('is_fsm', '=', True)]
            else:
                selected_models = [int(filter_value)]
        else:
            setting = self.env['ir.config_parameter'].sudo()
            model_ids_param = setting.get_param("timeline.customer_timeline_model_ids", "[]")
            try:
                selected_models = json.loads(model_ids_param) if model_ids_param else []
            except Exception:
                selected_models = []
        timeline_dict, model_stats, won_lead_total, won_lead_count = timeline._generate_timeline_data(selected_models, filter_domain)
        timeline_html = timeline._generate_timeline_html_content(timeline_dict, model_stats, won_lead_total, won_lead_count)
        return {
            'html': timeline_html,
            'filter': filter_value
        }

    def _get_split_filter_buttons_html(self):
        """Split filter buttons for mobile with task/service call handling"""
        setting = self.env['ir.config_parameter'].sudo()
        model_ids_param = setting.get_param("timeline.customer_timeline_model_ids", "[]")
        try:
            model_ids = json.loads(model_ids_param) if model_ids_param else []
        except Exception:
            return self._get_filter_buttons_html(), ""
        models = []
        if model_ids:
            for model_id in model_ids:
                try:
                    model = self.env['ir.model'].browse(model_id)
                    if model.exists():
                        if model.model == 'project.task':
                            models.append({
                                'id': f"{model.id}_task",
                                'name': 'Task',
                                'model': model.model
                            })
                            models.append({
                                'id': f"{model.id}_fsm",
                                'name': 'Service Call',
                                'model': model.model
                            })
                        else:
                            models.append({
                                'id': model.id,
                                'name': model.name,
                                'model': model.model
                            })
                except:
                    continue
        visible_count = 3
        visible_models = models[:visible_count]
        dropdown_models = models[visible_count:]
        visible_buttons = []
        all_selected_class = "selected_btn" if not self.active_filter or self.active_filter == 'all' else ""
        visible_buttons.append(f'''
            <button class="model_filter_btn {all_selected_class}" onclick="clearSelection(this)">
                All
            </button>
        ''')
        for model in visible_models:
            selected_class = "selected_btn" if self.active_filter == str(model['id']) else ""
            visible_buttons.append(f'''
                <button class="model_filter_btn {selected_class}" onclick="filterTimelineByModel('{model['id']}', this)">
                    {model['name']}
                </button>
            ''')
        visible_html = ''.join(visible_buttons)
        dropdown_buttons = []
        for model in dropdown_models:
            selected_class = "selected_btn" if self.active_filter == str(model['id']) else ""
            dropdown_buttons.append(f'''
                <button class="model_filter_btn {selected_class}" onclick="filterTimelineByModel('{model['id']}', this)">
                    {model['name']}
                </button>
            ''')
        dropdown_html = ''.join(dropdown_buttons)
        return visible_html, dropdown_html

    def _get_filter_buttons_html(self):
        """Modified to handle active filter state and split project.task"""
        setting = self.env['ir.config_parameter'].sudo()
        model_ids = setting.get_param("timeline.customer_timeline_model_ids", "[]")
        try:
            model_ids = json.loads(model_ids) if model_ids else []
        except Exception:
            model_ids = []
        if not model_ids:
            return "<div class='alert alert-warning text-center'>No models configured in Timeline settings.</div>"
        html_parts = ["""
        <div class="model_filter_container">
            <div class="filter_buttons_wrapper">
        """]
        is_all_active = "selected_btn" if (not self.active_filter or self.active_filter == 'all') else ""
        html_parts.append(f"""
            <button type="button" class="model_filter_btn {is_all_active}"
                onclick="clearSelection(this)">
                <span>All</span>
            </button>
        """)
        models = self.env['ir.model'].browse(model_ids)
        for model in models:
            if model.model == 'project.task':
                is_task_active = "selected_btn" if self.active_filter == f"{model.id}_task" else ""
                is_fsm_active = "selected_btn" if self.active_filter == f"{model.id}_fsm" else ""
                html_parts.append(f"""
                    <button type="button" class="model_filter_btn {is_task_active}" 
                        onclick="filterTimelineByModel('{model.id}_task', this)">
                        <span>Task</span>
                    </button>
                """)
                html_parts.append(f"""
                    <button type="button" class="model_filter_btn {is_fsm_active}" 
                        onclick="filterTimelineByModel('{model.id}_fsm', this)">
                        <span>Service Call</span>
                    </button>
                """)
            else:
                is_active = "selected_btn" if self.active_filter == str(model.id) else ""
                html_parts.append(f"""
                    <button type="button" class="model_filter_btn {is_active}" 
                        onclick="filterTimelineByModel({model.id}, this)">
                        <span>{model.name}</span>
                    </button>
                """)
        html_parts.append("""
            </div>
        </div>
        """)
        return "".join(html_parts)

    @api.depends("date_from", "date_to", "partner_id", "selected_model_ids")
    def _compute_timeline(self):
        """Keep this for backward compatibility if needed"""
        for rec in self:
            if not rec.partner_id or not rec.date_from or not rec.date_to:
                rec.activity_summary = ""
                continue
            selected_models = []
            try:
                if rec.selected_model_ids:
                    selected_models = rec.selected_model_ids.ids
            except (AttributeError, TypeError):
                selected_models = []
            if not selected_models:
                setting = self.env['ir.config_parameter'].sudo()
                model_ids_param = setting.get_param("timeline.customer_timeline_model_ids", "[]")
                try:
                    selected_models = json.loads(model_ids_param) if model_ids_param else []
                except Exception:
                    selected_models = []
            if not selected_models:
                rec.activity_summary = ""
                continue
            timeline_dict, model_stats, won_lead_total, won_lead_count = rec._generate_timeline_data(selected_models)
            rec.activity_summary = self._generate_inline_summary_html(model_stats, won_lead_total, won_lead_count)

    def _generate_timeline_data(self, model_ids, extra_domain=None):
        """Generate timeline data with support for extra domain filters, split won/non-won leads"""
        timeline_dict = defaultdict(list)
        model_stats = defaultdict(int)
        won_lead_total = 0.0
        won_lead_count = 0
        if not model_ids:
            return timeline_dict, model_stats, won_lead_total, won_lead_count
        start_dt = datetime.combine(self.date_from, datetime.min.time())
        end_dt = datetime.combine(self.date_to, datetime.max.time())
        max_per_model = 100
        for model_id in model_ids:
            try:
                model = self.env['ir.model'].browse(int(model_id))
                if not model or not model.model:
                    continue
                partner_fields = [
                    f for f in model.field_id
                    if f.ttype == "many2one" and f.relation == "res.partner" and
                       f.name in ["partner_id", "customer_id", "client_id"]]
                if not partner_fields:
                    continue
                if model.model == 'crm.lead':
                    for pf in partner_fields:
                        domain = [
                            (pf.name, "=", self.partner_id.id),
                            ("create_date", ">=", start_dt),
                            ("create_date", "<=", end_dt),
                        ]
                        if extra_domain:
                            domain.extend(extra_domain)
                        records = self.env[model.model].sudo().search(
                            domain,
                            order="create_date desc",
                            limit=max_per_model
                        )
                        for r in records:
                            date_key = r.create_date.date().isoformat() if r.create_date else "Unknown Date"
                            stage = self._get_record_stage(r, model.model)
                            if hasattr(r, 'probability') and hasattr(r, 'expected_revenue'):
                                if r.probability == 100:  # Won lead
                                    timeline_dict[date_key].append(("Lead/Opportunity-Won", r, model.model, stage))
                                    model_stats["Lead/Opportunity-Won"] += 1
                                    won_lead_total += r.expected_revenue or 0.0
                                    won_lead_count += 1
                                else:
                                    timeline_dict[date_key].append(("Lead/Opportunity", r, model.model, stage))
                                    model_stats["Lead/Opportunity"] += 1
                else:
                    for pf in partner_fields:
                        domain = [
                            (pf.name, "=", self.partner_id.id),
                            ("create_date", ">=", start_dt),
                            ("create_date", "<=", end_dt),
                        ]
                        if extra_domain:
                            domain.extend(extra_domain)
                        records = self.env[model.model].sudo().search(
                            domain,
                            order="create_date desc",
                            limit=max_per_model
                        )
                        for r in records:
                            date_key = r.create_date.date().isoformat() if r.create_date else "Unknown Date"
                            stage = self._get_record_stage(r, model.model)
                            # Use Service Call or Task heading
                            if model.model == 'project.task':
                                display_name = 'Service Call' if hasattr(r, 'is_fsm') and r.is_fsm else 'Task'
                            else:
                                display_name = model.name
                            timeline_dict[date_key].append((display_name, r, model.model, stage))
                            model_stats[display_name] += 1
            except Exception as e:
                continue
        return timeline_dict, model_stats, won_lead_total, won_lead_count

    def _get_record_stage(self, record, model_tech_name):
        """Get the current stage of a record based on its model type"""
        stage = ""
        try:
            if hasattr(record, 'stage_id') and record.stage_id:
                stage = record.stage_id.name
            elif hasattr(record, 'state'):
                stage = record.state
            elif hasattr(record, 'status'):
                stage = record.status
            elif model_tech_name == 'project.task' and hasattr(record, 'kanban_state'):
                stage = record.kanban_state
        except Exception as e:
            _logger.error("Error getting stage for record %s: %s", record, e)
            stage = ""
        return stage

    def _format_record_time(self, record):
        if not record.create_date:
            return self.env['ir.translation']._get_source(None, None, self.env.lang, 'Unknown time') or "Unknown time"
        return format_time(self.env, record.create_date, lang_code=self.env.user.lang)

    def _generate_timeline_html_content(self, timeline_dict, model_stats, won_lead_total=0.0, won_lead_count=0):
        """Generate the timeline content HTML (without buttons)"""
        if not timeline_dict:
            return """
              <div class="text-center py-5">
                  <div style="font-size: 48px; margin-bottom: 20px;">📝</div>
                  <h4>No Activities Found</h4>
                  <p class="text-muted">No records found for the selected customer and models in the specified date range.</p>
                  <p class="text-muted">Try adjusting your date range or model filters above.</p>
              </div>
              """

        # Get user timezone
        user_tz = self.env.user.tz or 'UTC'

        summary_html = self._generate_inline_summary_html(model_stats, won_lead_total)
        sorted_dates = sorted(timeline_dict.keys(), reverse=True)
        html_parts = [summary_html]
        html_parts.append("""
          <div class="timeline_content">
          """)
        for date_key in sorted_dates:
            try:
                date_obj = datetime.fromisoformat(date_key).date()
                formatted_date = date_obj.strftime("%A, %B %d, %Y")
            except:
                formatted_date = date_key
            activities_count = len(timeline_dict[date_key])
            html_parts.append(f"""
              <div class="timeline_date_section">
                  <div class="timeline_date_header collapsed" onclick="toggleDateSection(this)">
                      {formatted_date}
                      <span class="toggle_icon">▼</span>
                  </div>
                  <div class="timeline_models_container">
              """)
            model_groups = defaultdict(list)
            for model_name, record, model_tech_name, stage in timeline_dict[date_key]:
                model_groups[model_name].append((record, model_tech_name, stage))
            for model_name, records in model_groups.items():
                html_parts.append(f"""
                  <div class="model_group">
                      <div class="model_header" onclick="toggleModelGroup(this)">
                          {model_name}
                          <span class="record_count">{len(records)}</span>
                          <span class="toggle_icon">▼</span>
                      </div>
                      <div class="model_records">
                  """)
                for record_data in records:
                    record, model_tech_name, stage = record_data
                    record_time = self._format_record_time(record)
                    stage_html = ""
                    separator_html = ""

                    expected_value_html = ""
                    # Only show Expected Value if ONLY crm.lead is selected (not all models)
                    selected_model_ids = self.selected_model_ids.ids if self.selected_model_ids else []
                    crm_lead_model = self.env['ir.model'].search([('model', '=', 'crm.lead')], limit=1)
                    only_lead_selected = len(selected_model_ids) == 1 and crm_lead_model and crm_lead_model.id in selected_model_ids
                    if only_lead_selected and model_tech_name == 'crm.lead' and model_name in ['Lead/Opportunity', 'Lead/Opportunity-Won'] and hasattr(record, 'expected_revenue'):
                        expected_value = record.expected_revenue or 0.0
                        if expected_value > 0:
                            formatted_value = self.env['ir.qweb.field.monetary'].value_to_html(
                                expected_value,
                                {'display_currency': self.env.company.currency_id}
                            )
                            expected_value_html = f'<div class="expected_value">Expected Value: {formatted_value}</div>'
                    else:
                        expected_value_html = ""

                    customer_html = ""
                    if model_tech_name == 'crm.lead' and hasattr(record, 'partner_id') and record.partner_id:
                        customer_html = f'<div class="customer_name">Customer: {record.partner_id.display_name}</div>'

                    # Show check-in/check-out for account.analytic.line records
                    timesheet_html = ""
                    if model_tech_name == 'account.analytic.line':
                        check_in = getattr(record, 'date_time', None)
                        check_out = getattr(record, 'end_date_time', None)

                        if check_in or check_out:
                            timesheet_html = '<div class="timesheet_times">'

                            if check_in:
                                # Convert check_in from UTC to user timezone
                                check_in_utc = fields.Datetime.from_string(check_in)
                                check_in_local = fields.Datetime.context_timestamp(self.with_context(tz=user_tz),
                                                                                   check_in_utc)
                                check_in_formatted = check_in_local.strftime("%d-%m-%y %H:%M:%S")
                                timesheet_html += f'Check-in: {check_in_formatted} '

                            if check_out:
                                # Convert check_out from UTC to user timezone
                                check_out_utc = fields.Datetime.from_string(check_out)
                                check_out_local = fields.Datetime.context_timestamp(self.with_context(tz=user_tz),
                                                                                    check_out_utc)
                                check_out_formatted = check_out_local.strftime("%d-%m-%y %H:%M:%S")
                                timesheet_html += f'Check-out: {check_out_formatted}'

                            timesheet_html += '</div>'

                    if stage and stage.strip():
                        stage_class = "stage_default"
                        stage_display = stage
                        if stage_display and stage_display.lower() in ['done', 'completed', 'closed', 'finished', 'cancelled']:
                            stage_class = "stage_completed"
                        elif stage_display and stage_display.lower() in ['progress', 'in progress', 'working', 'in development', 'confirmed']:
                            stage_class = "stage_progress"
                        elif stage_display and stage_display.lower() in ['new', 'draft', 'new record']:
                            stage_class = "stage_new"
                        stage_html = f'<span class="record_stage {stage_class}">{stage_display}</span>'
                        separator_html = '<span class="record_separator"> - </span>'
                    html_parts.append(f"""
                      <div class="record_item">
                          <div class="record_name_line">
                              <span class="record_name">{record.display_name}</span>
                              {separator_html}
                              {stage_html}
                          </div>
                          {customer_html}
                          {expected_value_html}
                          {timesheet_html}
                          <div class="record_time">Created at {record_time}</div>
                      </div>
                      """)
                html_parts.append("</div></div>")
            html_parts.append("</div></div>")
        html_parts.append("</div>")
        return "".join(html_parts)

    def _generate_inline_summary_html(self, model_stats, won_lead_total=0.0, *args, **kwargs):
        """Generate inline summary at the top of timeline, show only expected value of won leads"""
        if not model_stats:
            return ""
        total_activities = sum(model_stats.values())
        formatted_won_total = self.env['ir.qweb.field.monetary'].value_to_html(
            won_lead_total,
            {'display_currency': self.env.company.currency_id}
        ) if won_lead_total > 0 else "0.00"
        html_parts = [f"""
        <div class="inline_summary">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h5 style="margin: 0; color: #495057;">Activity Summary</h5>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <div style="background: #875A7B; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 12px;">
                        Expected Value: {formatted_won_total}
                    </div>
                    <div style="background: #875A7B; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 12px;">
                        Total: {total_activities} activities
                    </div>
                </div>
            </div>
        """]
        if model_stats:
            html_parts.append("""
            <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
            """)
            for model_name, count in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_activities) * 100
                if model_name == 'Lead/Opportunity-Won':
                    badge_style = "background: white; border: 1px solid #dee2e6; color: #495057;"
                elif model_name == 'Lead/Opportunity':
                    badge_style = "background: white; border: 1px solid #dee2e6; color: #495057;"
                else:
                    badge_style = "background: white; border: 1px solid #dee2e6; color: #495057;"

                html_parts.append(f"""
                <span style="{badge_style} padding: 4px 8px; border-radius: 6px; font-size: 12px;">
                    {model_name}: <strong>{count}</strong> ({percentage:.1f}%)
                </span>
                """)
            html_parts.append("</div>")
        html_parts.append("</div>")
        return "".join(html_parts)

    def _get_empty_state_with_buttons(self):
        """Show a button that loads filters & timeline without customer"""
        return f"""
        <div class="unified_timeline_container">
            <div class="timeline_content_section" style="text-align:center; padding:50px;">
            </div>
        </div>
        """

    def _generate_summary_html(self, model_stats):
        """Generate summary statistics HTML for customer (legacy method)"""
        if not model_stats:
            return ""
        total_activities = sum(model_stats.values())
        html_parts = [f"""
        <div class="timeline_summary">
            <div class="summary_header">
                <h5>Activity Summary for {self.partner_id.display_name}</h5>
                <div class="total_count">Total: {total_activities} activities</div>
            </div>
        """]
        if model_stats:
            html_parts.append("""
            <div class="model_breakdown">
            """)
            for model_name, count in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_activities) * 100
                html_parts.append(f"""
                <div class="model_stat">
                    {model_name}: <strong>{count}</strong> ({percentage:.1f}%)
                </div>
                """)
            html_parts.append("</div>")
        html_parts.append("</div>")
        return "".join(html_parts)

    @api.model
    def default_get(self, fields_list):
        """Set smart defaults for customer"""
        defaults = super().default_get(fields_list)
        if self._context.get('active_model') == 'res.partner' and self._context.get('active_id'):
            partner = self.env['res.partner'].browse(self._context['active_id'])
            if partner.exists() and partner.customer_rank > 0:
                defaults['partner_id'] = partner.id
        if 'selected_model_ids' in fields_list:
            setting = self.env['ir.config_parameter'].sudo()
            model_ids = setting.get_param("timeline.customer_timeline_model_ids", "[]")
            try:
                model_ids = json.loads(model_ids) if model_ids else []
                if model_ids:
                    defaults['selected_model_ids'] = [(6, 0, model_ids)]
                else:
                    defaults['selected_model_ids'] = []
            except Exception:
                defaults['selected_model_ids'] = []
        return defaults

    def action_export_timeline(self):
        """Export timeline data for customer"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Export functionality coming soon!',
                'type': 'info',
                'sticky': False,
            }
        }
