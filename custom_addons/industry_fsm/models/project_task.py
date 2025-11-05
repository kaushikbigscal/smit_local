# -*- coding: utf-8 -*-
import datetime
from datetime import timedelta, datetime, time, date
from typing import Dict, List
import pytz
import requests
import re
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo import Command, fields, models, api, _
from odoo.osv import expression
from odoo.tools import get_lang, json, html_escape, Markup
from odoo.addons.project.models.project_task import CLOSED_STATES
from odoo.tools import html2plaintext
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskReopenLog(models.Model):
    _name = 'project.task.reopen.log'
    _description = 'Re-Open Task Log'

    task_id = fields.Many2one('project.task', string="Task", required=True, ondelete='cascade')
    reopen_time = fields.Datetime(string="Re-Open Time", default=fields.Datetime.now, required=True)
    reason = fields.Char(string="Reason", required=True)


class ProjectTaskReopenWizard(models.TransientModel):
    _name = 'project.task.reopen.wizard'
    _description = 'Task Re-open Wizard'

    task_id = fields.Many2one('project.task', string="Task", required=True)
    reopen_reason = fields.Char(string="Re-open Reason", required=True, tracking=True)
    user_ids = fields.Many2many(
        'res.users', string="Assign Users", required=True,
        domain="[('department_id', '=', department_id)]",
        default=lambda self: self._default_assign_users(),
    )

    department_id = fields.Many2one(
        'hr.department', string="Department",
        domain=lambda self: self._get_department_domain(),
        default=lambda self: self._default_department()
    )

    @api.model
    def _get_department_domain(self):
        parent_department = self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
        return [('parent_id', '=', parent_department.id)] if parent_department else []

    @api.model
    def _default_assign_users(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            task = self.env['project.task'].browse(active_id)
            return task.user_ids.ids
        return []

    @api.model
    def _default_department(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            task = self.env['project.task'].browse(active_id)
            return task.department_id.id if task.department_id else False
        return False

    def action_confirm_reopen(self):
        self.ensure_one()

        task = self.task_id
        task.reopen_reason = self.reopen_reason

        if self.user_ids:
            task.user_ids = [(6, 0, self.user_ids.ids)]
        if self.department_id:
            task.department_id = self.department_id
        self.env['project.task.reopen.log'].create({
            'task_id': task.id,
            'reason': self.reopen_reason,
        })

        task.reopen_count += 1

        reopened_stage = self.env['project.task.type'].search([
            ('name', '=', 'Assigned'),
            ('project_ids.is_fsm', '=', True)
        ], limit=1)
        if reopened_stage:
            task.stage_id = reopened_stage.id

        return {'type': 'ir.actions.act_window_close'}


class Task(models.Model):
    _inherit = "project.task"

    def _get_user_fsm_role(self):
        """
        Determine the FSM role of the current user.
        Returns the highest priority role.
        Priority: Manager > Supervisor > Task Creator > User
        """
        user = self.env.user

        if user.has_group('industry_fsm.group_fsm_manager'):
            return 'manager'
        elif user.has_group('industry_fsm.group_fsm_supervisor'):
            return 'supervisor'
        elif user.has_group('industry_fsm.group_fsm_task_creator'):
            return 'task_creator'
        elif user.has_group('industry_fsm.group_fsm_user'):
            return 'user'

        return None

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        is_fsm_mode = self._context.get('fsm_mode')
        if is_fsm_mode:
            result['is_fsm'] = True
        if 'project_id' in fields_list and not result.get('project_id') and is_fsm_mode:
            company_id = self.env.context.get('default_company_id') or self.env.company.id
            fsm_project = self.env['project.project'].search([
                ('is_fsm', '=', True),
                ('company_id', '=', company_id)
            ], order='sequence', limit=1)
            if fsm_project:
                result['stage_id'] = self.stage_find(fsm_project.id, [('fold', '=', False)])
                result['project_id'] = fsm_project.id
                result['company_id'] = company_id
                result["planned_date_begin"] = datetime.now()
                result["date_deadline"] = datetime.now()

                if 'service_types' in fields_list and not result.get('service_types'):
                    default_service_type = self.env['service.type'].search([
                        ('default_in_call', '=', True)
                    ], limit=1)
                    if default_service_type:
                        result['service_types'] = default_service_type.id

                # if 'department_id' in fields_list and not result.get('department_id'):
                #     user_dept = self.env.user.employee_id.department_id
                #     if user_dept:
                #         # # Check if department is allowed by the domain
                #         allowed_ids = self.env['hr.department'].search(self._get_department_domain()).ids
                #         if user_dept.id in allowed_ids:
                #             result['department_id'] = user_dept.id

                # ============================================================
                # AUTO-ASSIGNMENT LOGIC BASED ON USER GROUP
                # ============================================================
                user = self.env.user

                # Check if user has employee record with department
                if user.employee_id and user.employee_id.department_id:
                    user_dept = user.employee_id.department_id
                    role = self._get_user_fsm_role()

                    # Check if department field should be populated
                    if 'department_id' in fields_list and not result.get('department_id'):
                        # Check if department is allowed by the domain
                        allowed_ids = self.env['hr.department'].search(self._get_department_domain()).ids

                        if user_dept.id in allowed_ids:
                            # Apply rules based on user role
                            if role == 'manager':
                                # Manager: Leave department blank
                                pass

                            elif role == 'supervisor':
                                # Supervisor: Set department only
                                result['department_id'] = user_dept.id

                            elif role == 'task_creator':
                                # Task Creator: Set department
                                result['department_id'] = user_dept.id

                    # Check if assignee field should be populated
                    if role == 'task_creator':
                        # Task Creator: Assign to self
                        result['user_ids'] = [(6, 0, [user.id])]
                        _logger.info(f"Task Creator: Set user_ids to {result['user_ids']}")
                    elif 'user_ids' in fields_list:
                        # For other roles, only set to False if in fields_list
                        result['user_ids'] = False
                else:
                    # If no employee/department, set user_ids to False
                    if 'user_ids' in fields_list:
                        result['user_ids'] = False
                # ============================================================

        return result

    is_fsm = fields.Boolean(related='project_id.is_fsm', search='_search_is_fsm')
    fsm_done = fields.Boolean("Task Done", compute='_compute_fsm_done', readonly=False, store=True, copy=False)
    # Use to count conditions between : time, worksheet and materials
    # If 2 over 3 are enabled for the project, the required count = 2
    # If 2 over 3 are enabled for the project, the required count = 2
    # If 1 over 3 is met (enabled + encoded), the satisfied count = 2
    display_enabled_conditions_count = fields.Integer(compute='_compute_display_conditions_count')
    display_satisfied_conditions_count = fields.Integer(compute='_compute_display_conditions_count')
    display_mark_as_done_primary = fields.Boolean(compute='_compute_mark_as_done_buttons')
    display_mark_as_done_secondary = fields.Boolean(compute='_compute_mark_as_done_buttons')
    partner_phone = fields.Char(
        compute='_compute_partner_phone', inverse='_inverse_partner_phone',
        string="Phone / Mobile", readonly=False, store=True, copy=False, tracking=True
    )

    partner_city = fields.Char(related='partner_id.city', readonly=False)
    is_task_phone_update = fields.Boolean(compute='_compute_is_task_phone_update')
    # <!--            for internal and external repair -->
    sequence_fsm = fields.Char(string='Ticket Number', readonly=True,
                               store=True, recursive=True)
    date_time = fields.Datetime(
        string="Start Time", default=fields.Datetime.now, copy=False
    )

    is_stage_planned = fields.Boolean(
        compute='_compute_is_stage_planned',
        store=False  # Optional: can be stored if used often
    )

    has_planned_date_changed = fields.Boolean("Date Changed", default=False)

    @api.model
    def get_fsm_calendar_view_id(self):
        """Get the FSM calendar form view ID"""
        try:
            view = self.env.ref('industry_fsm.view_fsm_task_calendar_form')
            return view.id if view else False
        except ValueError:
            # View reference not found
            return False

    @api.depends('stage_id')
    def _compute_is_stage_planned(self):
        for rec in self:
            rec.is_stage_planned = rec.stage_id.name in ['New', 'Assigned']

    @api.onchange('planned_date_begin', 'date_deadline')
    def _onchange_planned_date_begin(self):
        for rec in self:
            rec.has_planned_date_changed = True

    def action_set_stage_planned(self):
        """Set stage to 'Planned' when button is clicked"""
        planned_stage = self.env['project.task.type'].search([
            ('name', '=', 'Planned')
        ], limit=1)

        if not planned_stage:
            raise UserError("No stage named 'Planned' exists!")

        self.write({
            'stage_id': planned_stage.id,
            'has_planned_date_changed': False
        })

        return True

    @api.model
    def create(self, vals):
        """Check create permissions for supervisors"""
        user = self.env.user

        # Allow all users to create non-FSM tasks
        if not self._context.get('fsm_mode'):
            pass

        if self._context.get('fsm_mode'):
            # Admins should have full access
            if user.has_group('industry_fsm.group_fsm_manager'):
                pass

            # Block normal FSM users from creating FSM tasks
            if self._context.get('fsm_mode'):
                if user.has_group('industry_fsm.group_fsm_user') and \
                        not user.has_group('industry_fsm.group_fsm_supervisor') and \
                        not user.has_group('industry_fsm.group_fsm_manager') and \
                        not user.has_group('industry_fsm.group_fsm_task_creator'):
                    raise AccessError(_("Normal FSM users are not allowed to create FSM tasks."))

            # Additional checks for supervisors
            if vals.get('department_id') and user.has_group('industry_fsm.group_fsm_supervisor'):
                employee = user.employee_id
                if employee and employee.department_id and employee.department_id.id == vals['department_id']:
                    pass  # Allow creation in user's own department
                else:
                    allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('create')
                    if vals['department_id'] not in allowed_dept_ids:
                        dept_name = self.env['hr.department'].browse(vals['department_id']).name
                        raise AccessError(_("You do not have create access for department '%s'.") % dept_name)

            if not vals.get('user_ids') and user.has_group(
                    'industry_fsm.group_fsm_task_creator') and not user.has_group('industry_fsm.group_fsm_supervisor'):
                raise ValidationError("You cannot create call without assignee.")

            if vals.get('call_sub_types') == 'escalation_call':
                raise ValidationError("You cannot select 'Escalation Call' while creating a new call.")

            if vals.get('parent_id') and not vals.get('customer_product_id'):
                vals = self._inherit_parent_task_fields(vals)

        result = super(Task, self).create(vals)

        # Generate sequence after creation
        if result.parent_id:
            result.sequence_fsm = result.parent_id.sequence_fsm
        elif result.is_fsm and not result.sequence_fsm:
            result.sequence_fsm = self.env['ir.sequence'].next_by_code('service.call') or ""

        # For each newly created task that has a parent_id
        for task in result.filtered(lambda t: t.parent_id):
            parent = task.parent_id
            task.parent_id = False
            task.parent_id = parent

        if result.is_fsm:
            # Dhruti
            # Get the 'New' stage
            new_stage = self.env['project.task.type'].search([
                ('name', '=', 'New'),
                ('project_ids.is_fsm', '=', True)
            ], limit=1)

            if new_stage and result.stage_id.id == new_stage.id:
                # Fetch WhatsApp template for 'New' stage
                whatsapp_template = self.env['template.whatsapp'].search([
                    ('model_id.model', '=', 'project.project'),
                    ('project_id', '=', result.project_id.id),
                    ('stage_id', '=', new_stage.id),
                ], limit=1)

                if whatsapp_template and whatsapp_template.message:
                    result.send_whatsapp_notification(whatsapp_template)
                else:
                    print(
                        f"?? No WhatsApp template found for project '{result.project_id.name}', stage 'New'."
                    )

        return result

    def _inherit_parent_task_fields(self, vals):
        parent_task = self.env['project.task'].browse(vals['parent_id'])

        # Direct fields
        simple_fields = [
            'call_sub_types', 'planned_date_begin', 'date_deadline',
            'problem_description', 'fix_description',
            'unit_status', 'call_allocation'
        ]
        for field in simple_fields:
            if not vals.get(field) and getattr(parent_task, field):
                vals[field] = getattr(parent_task, field)

        # Many2one fields
        m2o_fields = [
            'call_type', 'call_coordinator_id', 'service_types', 'department_id', 'vendor_id', 'serial_number'
        ]
        for field in m2o_fields:
            if not vals.get(field) and getattr(parent_task, field):
                vals[field] = getattr(parent_task, field).id

        # Many2many fields
        m2m_fields = [
            'complaint_type_id', 'reason_code_id', 'tag_ids'
        ]
        for field in m2m_fields:
            if not vals.get(field) and getattr(parent_task, field):
                vals[field] = [(6, 0, getattr(parent_task, field).ids)]

        # Special handling for customer_product_id
        if parent_task.customer_product_id:
            vals['customer_product_id'] = parent_task.customer_product_id.id

        return vals

    service_types = fields.Many2one(comodel_name='service.type', string='Service Type', tracking=True)

    pending_reason = fields.Many2one(comodel_name='pending.reason', string='Pending Reason', tracking=True)
    stage_id = fields.Many2one('project.task.type', string="Stage")
    is_pending_stage = fields.Boolean(compute='_compute_is_pending_stage', store=True)

    is_work_started = fields.Boolean(string="Work Started", default=False)

    reopen_count = fields.Integer(string="Re-Open Count", default=0)
    reopen_log_ids = fields.One2many('project.task.reopen.log', 'task_id', string="Re-Open Logs")
    reopen_reason = fields.Char(string="Reopen Reason", tracking=True)
    complaint_type_id = fields.Many2many(
        comodel_name='complaint.type',
        string='Complaint Type', tracking=True
    )
    reason_code_id = fields.Many2many(
        comodel_name='reason.code',
        string='Reason Code',
        domain="[('complaint_type_id', 'in', complaint_type_id)]", tracking=True
    )
    problem_description = fields.Char(string="Actual Problem", tracking=True)
    fix_description = fields.Char(string="Problem Solution", tracking=True)

    actual_problem = fields.Many2many(comodel_name='actual.problem', string='Actual Problems')
    date_time = fields.Datetime(string="Start Time", default=fields.Datetime.now, copy=False)

    @api.onchange('actual_problem')
    def _onchange_actual_problem(self):
        if not self.problem_description:
            self.problem_description = ''

        current_desc = self.problem_description.strip()

        # Check if each actual_problem name is already in the text (loose match)
        for name in self.actual_problem.mapped('name'):
            if name not in current_desc:
                # Append with comma if needed
                if current_desc and not current_desc.endswith(','):
                    self.problem_description += ', '
                self.problem_description += name

    call_allocation = fields.Selection([
        ('internal', 'Internal'),
        ('external', 'External')
    ], string="Allocation", default='internal', tracking=True)

    department_id = fields.Many2one(
        'hr.department', string="Department",
        domain=lambda self: self._get_department_domain(),
        tracking=True, invisible="is_fsm != True"
    )

    user_ids_domain = fields.Many2many(
        'res.users', compute='_compute_user_ids_domain', store=False
    )

    #####################################################################

    user_department_id = fields.Many2one(
        'hr.department',
        compute='_compute_user_department',  # How to calculate its value
        search='_search_user_department',  # How to search using this field
        string='My Department'
    )

    def _search_user_department(self, operator, value):
        user = self.env.user  # Get the currently logged-in user

        # Check if user has an employee record and a department
        if user.employee_id and user.employee_id.department_id:
            # Return the REAL domain: filter by the user's department
            return [('department_id', '=', user.employee_id.department_id.id)]

        # If user has no department, return a domain that matches nothing
        return [('id', '=', False)]

    ############################################################################

    @api.model
    def _get_department_domain(self):
        parent_department = self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
        if parent_department:
            child_departments = self.env['hr.department'].search([('parent_id', '=', parent_department.id)])
            dept_ids = child_departments.ids + [parent_department.id]
            return [('id', 'in', dept_ids)]
        return []

    @api.depends('department_id', 'is_fsm')
    def _compute_user_ids_domain(self):
        """Restrict available users based on department selection and FSM flag."""
        for task in self:
            if task.is_fsm:
                parent_department = self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
                sub_departments = self.env['hr.department'].search(
                    [('id', 'child_of', parent_department.id)]).ids if parent_department else []

                if task.department_id:
                    # Users from selected department
                    users = self.env['hr.employee'].search([
                        ('department_id', '=', task.department_id.id),
                        ('user_id', '!=', False)
                    ]).mapped('user_id').ids
                else:
                    # Users from 'Service Division' and its sub-departments
                    users = self.env['hr.employee'].search([
                        ('department_id', 'in', sub_departments),
                        ('user_id', '!=', False)
                    ]).mapped('user_id').ids

                task.user_ids_domain = [(6, 0, users)]  # Assign filtered users
            else:
                # Default domain: Only active, non-shared users for normal tasks
                users = self.env['res.users'].search([('share', '=', False), ('active', '=', True)]).ids
                task.user_ids_domain = [(6, 0, users)]

    @api.depends('stage_id')
    def _compute_is_pending_stage(self):
        pending_stage = self.env['project.task.type'].search([
            ('name', '=', 'Pending'),
            ('project_ids.is_fsm', '=', True)  # Direct filter for is_fsm projects
        ], limit=1)

        for record in self:
            record.is_pending_stage = (record.stage_id == pending_stage)

    @api.onchange('user_ids')
    def _onchange_user_assign(self):
        if self.project_id.is_fsm:

            if self.user_ids:
                assign_stage = self.env['project.task.type'].search([
                    ('name', '=', 'Assigned'),
                    ('project_ids', '=', self.project_id.id)
                ], limit=1)

                if assign_stage:
                    self.stage_id = assign_stage.id

    @api.onchange('complaint_type_id')
    def _onchange_complaint_type_id(self):
        """Clear Reason Code when Complaint Type changes."""
        self.reason_code_id = False

    readonly_fields = fields.Boolean(compute="_compute_readonly_fields", store=False)

    @api.depends_context('uid')
    def _compute_readonly_fields(self):
        user = self.env.user
        for rec in self:
            rec.readonly_fields = not (
                    user.has_group('industry_fsm.group_fsm_supervisor') or
                    user.has_group('industry_fsm.group_fsm_manager')
            )

    assignee_location = fields.Char(
        compute='_compute_assignee_location',
        store=False,
        readonly=True,
    )

    @api.depends('user_ids')
    def _compute_assignee_location(self):
        for rec in self:
            locations = []
            for user in rec.user_ids:
                employee = self.env['hr.employee'].sudo().search([('user_id', 'in', user.ids)], limit=1)
                if employee:
                    city = employee.private_city or ''
                    state = employee.private_state_id.name or ''
                    if city and state:
                        locations.append(f"{city}, {state}")
                    elif city or state:
                        locations.append(city or state)
            rec.assignee_location = '; '.join(locations)

    remark = fields.Char(comodel_name="res.partner", readonly=True, compute="_compute_partner_remark",
                         string="Customer Remark")

    @api.depends('partner_id.remark')
    def _compute_partner_remark(self):
        for task in self:
            self.remark = task.partner_id.remark

    vendor_id = fields.Many2one('res.partner', string="Vendor", domain="[('supplier_rank', '>', 0)]", tracking=True)
    show_vendor = fields.Boolean(compute="_compute_show_vendor", store=False)
    vendor_address = fields.Char(
        string="Vendor Address",
        compute="_compute_vendor_address",
        store=True,
        tracking=True
    )

    @api.depends('call_allocation')
    def _compute_show_vendor(self):
        for task in self:
            task.show_vendor = task.call_allocation == 'external'

    @api.depends('vendor_id')
    def _compute_vendor_address(self):
        for task in self:
            if task.vendor_id:
                task.vendor_address = f"{task.vendor_id.street or ''},{task.vendor_id.city or ''}, {task.vendor_id.country_id.name or ''}"
            else:
                task.vendor_address = ""

    # <!--            for internal and external repair -->

    service_charge_ids = fields.One2many("service.charge", "task_id", string="Service Charges")
    total_charge = fields.Float(string="Total Charge", compute="_compute_total_charge", store=True)
    paid_amount = fields.Float(string="Paid Amount", compute="_compute_paid_amount", store=True)
    remaining_amount = fields.Float(string="Remaining Amount", compute="_compute_remaining_amount", store=True)
    payment_status = fields.Selection([
        ('notpaid', 'Not Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid')
    ], string="Payment Status", store=True, default="notpaid")
    currency_id = fields.Many2one("res.currency", string="Currency")
    journal_entry_id = fields.Many2one("account.move", string="Journal Entry")
    service_charge_type = fields.Many2one("service.charge.type", string="Service Charge Type")
    show_register_payment_button = fields.Boolean(compute="_compute_show_register_payment_button")
    is_chargeable = fields.Boolean(compute="_compute_is_chargeable", store=False)
    # call_type = fields.Selection(
    #     selection=[('warranty', 'Warranty'), ('amc', 'AMC'), ('chargeable', 'Chargeable'), ('free', 'Free'),
    #                ('project', 'Project')],
    #     string="Call Type",
    #     readonly=False,
    #     tracking=True
    # )
    call_type = fields.Many2one(
        comodel_name='call.type',
        string="Call Type",
        readonly=False,
        tracking=True
    )
    move_id = fields.Many2one('account.move', string='Journal Entry')

    @api.depends("service_charge_ids")
    def _compute_show_register_payment_button(self):
        for task in self:
            task.show_register_payment_button = bool(
                task.service_charge_ids) and not task._origin  # Show the button if at least one service charge exists

    @api.depends("service_charge_ids.amount")
    def _compute_total_charge(self):
        for task in self:
            task.total_charge = sum(task.service_charge_ids.mapped("amount"))

    @api.depends("total_charge")
    def _compute_paid_amount(self):
        for task in self:
            payments = self.env["account.payment"].search([
                ("task_id", "=", task.id),
                ("state", "=", "posted")
            ])
            task.paid_amount = sum(payments.mapped("amount")) if payments else 0.0

    @api.depends("total_charge", "paid_amount")
    def _compute_remaining_amount(self):
        for task in self:
            task.remaining_amount = (task.total_charge) - (task.paid_amount)

    @api.depends("remaining_amount", "paid_amount")
    def _compute_payment_status(self):
        for task in self:
            if task.paid_amount == 0:
                task.payment_status = "notpaid"
            elif task.remaining_amount <= 0:
                task.payment_status = "paid"
            elif task.paid_amount > 0:
                task.payment_status = "partial"
            else:
                task.payment_status = "notpaid"

    @api.onchange("service_charge_ids")
    def _onchange_service_charge_ids(self):
        self._compute_total_charge()
        self._compute_remaining_amount()

    @api.depends("call_type")
    def _compute_is_chargeable(self):
        chargeable = self.env.ref('industry_fsm.call_type_chargeable', raise_if_not_found=False)
        for task in self:
            # task.is_chargeable = task.call_type == 'chargeable'
            if chargeable:
                task.is_chargeable = bool(task.call_type and task.call_type.id == chargeable.id)
            else:
                task.is_chargeable = bool(
                    task.call_type and (task.call_type.name or '').strip().lower() == 'chargeable')

    def action_open_payment_wizard(self):
        if not self.service_charge_ids:
            raise UserError("Service Charge is Empty.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Register Payment',
            'res_model': 'service.call.payment.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('industry_fsm.view_service_call_payment_wizard_form').id,
            'target': 'new',
            'context': {'default_task_id': self.id}
        }

    # =================================== joint call ==============

    call_sub_types = fields.Selection([
        ('normal_call', 'Normal Calls'),
        ('join_call', 'Join Calls'),
        ('escalation_call', 'Escalation Calls')
    ], string="Call Sub Type", default='normal_call', tracking=True)

    is_join_call = fields.Boolean(string="Is Join Call", compute='_compute_is_join_call', store=True, readonly=True)

    @api.onchange('call_sub_types')
    def _onchange_call_sub_types(self):
        if not self._origin:
            return

        previous_type = self._origin.call_sub_types
        new_type = self.call_sub_types

        if previous_type == 'join_call' and new_type != 'join_call':
            if self.reopen_log_ids:
                self.reopen_log_ids.unlink()

            timesheet_count = self.env['account.analytic.line'].search_count([
                ('task_id', '=', self.id)
            ])
            subcall_count = len(self.child_ids)

            if timesheet_count > 0 or subcall_count > 0:
                self.call_sub_types = 'join_call'

                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _(
                            "To change the Call Type from 'Join Call' to another type, "
                            "please delete timesheet entries, remove sub-calls and Re-open logs first."
                        )
                    }
                }

    @api.depends('call_sub_types')
    def _compute_is_join_call(self):
        for task in self:
            if task.is_fsm:
                task.is_join_call = task.call_sub_types == 'join_call'

    parent_id = fields.Many2one('project.task', string="Parent Task")
    task_ids = fields.One2many(
        'project.task',
        'parent_id',
        string="Sub-Calls", domain="[('is_fsm','=', True)]"
    )
    user_ids = fields.Many2many('res.users', relation='project_task_user_rel', column1='task_id', column2='user_id',
                                string='Assignees', context={'active_test': False},
                                )
    blocked_by = fields.Many2one(
        'project.task',
        string="Task Blocked By",
        domain="[('id', 'in', available_subtasks)]"
    )
    show_blocked_by = fields.Boolean(
        compute="_compute_service_call_dependencies",
        store=False)

    def _compute_service_call_dependencies(self):
        config_param = self.env['ir.config_parameter'].sudo().get_param('industry_fsm.service_call_dependencies')
        for task in self:
            task.show_blocked_by = bool(config_param)

    available_subtasks = fields.Many2many(
        'project.task',
        compute="_compute_available_subtasks",
        string="Available Subtasks"
    )

    @api.constrains('user_ids')
    def _check_single_user(self):
        for record in self:
            if record.is_fsm and len(record.user_ids) > 1:
                raise ValidationError("You can only assign one user.")

    # @api.onchange('department_id')
    # def _onchange_department_id(self):
    #     self.user_ids = [(5, 0, 0)]

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Clear user_ids when department changes"""

        # Get user role
        role = self._get_user_fsm_role()

        # For task_creator on new records: only clear if they manually changed department
        if not self.id and role == 'task_creator':
            # Check if the current department matches user's department (auto-assigned)
            if self.env.user.employee_id and self.env.user.employee_id.department_id:
                if self.department_id == self.env.user.employee_id.department_id:
                    # Department matches user's department - this is auto-assignment, don't clear
                    return

        # Clear the assignees
        self.user_ids = [(5, 0, 0)]

    @api.constrains('call_sub_types', 'task_ids')
    def _check_joint_call_has_subtasks(self):
        for task in self:
            if not task.parent_id and task.call_sub_types == 'join_call' and not task.task_ids:
                raise ValidationError("At least one joint call (sub-call) is required when 'Join Call' is selected.")

    @api.depends('parent_id', 'is_fsm')
    def _compute_available_subtasks(self):
        for task in self:
            if task.is_fsm and task.parent_id:
                related_tasks = task.parent_id.child_ids | task.parent_id
                task.available_subtasks = related_tasks.filtered(lambda t: t.id != task.id)
            else:
                task.available_subtasks = False

    def action_create_new_service_call(self):
        """Create a new Service Call (Task) and open the form view"""
        self.ensure_one()  # Ensure only one record is processed at a time
        return {
            'name': "New Service Call",
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.id,  # Open the newly created service call
            'target': 'current',
        }

    def action_open_sub_calls(self):
        self.ensure_one()
        domain = [
            ('parent_id', '=', self.id),
            ('is_fsm', '=', True),
        ]
        sub_tasks = self.env['project.task'].search(domain)

        if len(sub_tasks) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sub-Call',
                'res_model': 'project.task',
                'res_id': sub_tasks.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sub-Calls',
                'res_model': 'project.task',
                'view_mode': 'tree,form',
                'domain': domain,
                'context': {
                    'default_parent_id': self.id,
                    'default_is_fsm': True,
                    'default_user_ids': self.user_ids.mapped('id'),
                    'subtask_action': True,
                },
                'target': 'current',
            }

    subtask_count = fields.Integer(compute="_compute_subtask_count", string="Sub-Call Count")
    closed_subtask_count = fields.Integer(compute="_compute_subtask_count", string="Closed Sub-Call Count")

    CLOSED_STAGES = ["Done", "Cancelled"]
    CLOSED_STATES = {
        '1_done': 'Done',
        '1_canceled': 'Canceled',
    }

    @api.depends('task_ids', 'task_ids.stage_id')
    def _compute_subtask_count(self):
        for task in self:
            if task.is_fsm:
                sub_tasks = task.task_ids.filtered(lambda t: t.is_fsm)
                task.subtask_count = len(sub_tasks)
                task.closed_subtask_count = len(sub_tasks.filtered(lambda t: t.stage_id.name in self.CLOSED_STAGES))
            else:
                task.subtask_count = len(task.task_ids)
                task.closed_subtask_count = len(task.task_ids.filtered(lambda t: t.state in self.CLOSED_STATES))

    def action_partner_navigate(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id.action_partner_navigate()
        else:
            raise UserError("No customer selected on this task.")

    def open_full_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task',
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',  # Or 'new' if you want it to open in a dialog
        }

    # ====================================================

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS | {'is_fsm',
                                               'planned_date_begin',
                                               'fsm_done',
                                               'partner_phone',
                                               'partner_city', }

    @api.depends(
        'fsm_done', 'is_fsm', 'display_enabled_conditions_count', 'display_satisfied_conditions_count')
    def _compute_mark_as_done_buttons(self):
        for task in self:
            primary, secondary = True, True
            if task.fsm_done or not task.is_fsm:  # or task.timer_start
                primary, secondary = False, False
            else:
                if task.display_enabled_conditions_count == task.display_satisfied_conditions_count:
                    secondary = False
                else:
                    primary = False
            task.update({
                'display_mark_as_done_primary': primary,
                'display_mark_as_done_secondary': secondary,
            })

    @api.depends('partner_id.phone', 'partner_id.mobile')
    def _compute_partner_phone(self):
        for task in self:
            phone_numbers = filter(None, [task.partner_id.phone, task.partner_id.mobile])  # Remove empty values
            task.partner_phone = ', '.join(phone_numbers) if phone_numbers else False  # Join phone & mobile

    def _inverse_partner_phone(self):
        for task in self:
            if task.partner_id and task.partner_phone:
                numbers = task.partner_phone.split(',')  # Split the saved value
                task.partner_id.phone = numbers[0] if len(numbers) > 0 else False
                task.partner_id.mobile = numbers[1] if len(numbers) > 1 else False

    @api.depends('partner_phone', 'partner_id.phone', 'partner_id.mobile')
    def _compute_is_task_phone_update(self):
        for task in self:
            combined_phone = ', '.join(filter(None, [task.partner_id.phone, task.partner_id.mobile]))  # Match format
            task.is_task_phone_update = task.partner_phone != combined_phone

    @api.depends('project_id.allow_timesheets', 'total_hours_spent')
    def _compute_display_conditions_count(self):
        for task in self:
            enabled = 1 if task.project_id.allow_timesheets else 0
            satisfied = 1 if enabled and task.total_hours_spent else 0
            task.update({
                'display_enabled_conditions_count': enabled,
                'display_satisfied_conditions_count': satisfied
            })

    @api.depends('fsm_done', 'display_timesheet_timer', 'timer_start', 'total_hours_spent')
    def _compute_display_timer_buttons(self):
        fsm_done_tasks = self.filtered(lambda task: task.fsm_done)
        fsm_done_tasks.update({
            'display_timer_start_primary': False,
            'display_timer_start_secondary': False,
            'display_timer_stop': False,
            'display_timer_pause': False,
            'display_timer_resume': False,
        })
        super(Task, self - fsm_done_tasks)._compute_display_timer_buttons()

    @api.model
    def _search_is_fsm(self, operator, value):
        query = """
            SELECT p.id
            FROM project_project P
            WHERE P.active = 't' AND P.is_fsm
        """
        operator_new = operator == "=" and "inselect" or "not inselect"
        return [('project_id', operator_new, (query, ()))]

    # TODO: remove in master
    def _onchange_planned_date(self):
        return

    def write(self, vals):
        """Check write permissions for supervisors"""

        # Additional restrictions for supervisors (existing logic)

        user = self.env.user

        # # Admins should have full access
        if user.has_group('industry_fsm.group_fsm_manager'):
            pass

        for task in self:
            if task.is_fsm and task.department_id:
                task.check_department_permission('write')

            # Additional restrictions for supervisors
            if vals.get('department_id') and \
                    user.has_group('industry_fsm.group_fsm_supervisor') and \
                    user.id not in vals.get('user_ids', []):
                employee = user.employee_id
                if employee and employee.department_id and employee.department_id.id == vals['department_id']:
                    continue  # Allow write in user's own department

                allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('write')
                if vals['department_id'] not in allowed_dept_ids:
                    dept_name = self.env['hr.department'].browse(vals['department_id']).name
                    raise AccessError(_("You do not have write access for department '%s'.") % dept_name)

        self_fsm = self.filtered('is_fsm')
        super(Task, self - self_fsm).write(vals.copy())
        for task in self:
            if 'call_type' in vals:
                # if task.service_charge_ids and vals.get('call_type') != 'chargeable':
                new_call_type_id = vals.get('call_type')
                chargeable = self.env.ref('industry_fsm.call_type_chargeable', raise_if_not_found=False)
                is_new_chargeable = bool(chargeable and new_call_type_id == chargeable.id)
                if task.service_charge_ids and not is_new_chargeable:
                    raise ValidationError(
                        "You cannot change Call Type after adding Service Charge unless you set it to 'chargeable'."
                    )

        project = self.env['project.project'].search([('is_fsm', '=', True)], limit=1).id

        resolved_stage = self.env['project.task.type'].search([
            ('name', '=', 'Resolved'),
            ('project_ids', 'in', [project])
        ], limit=1).id
        done_stage = self.env['project.task.type'].search([
            ('name', '=', 'Done'),
            ('project_ids', 'in', [project])
        ], limit=1).id

        in_progress_stage = self.env['project.task.type'].search([
            ('name', '=', 'In Progress'),
            ('project_ids.is_fsm', '=', True)
        ], limit=1)

        service_resolved_stage = self.env['ir.config_parameter'].sudo().get_param(
            'industry_fsm.service_resolved_stage', default='False') == 'True'

        validation_stage = done_stage if service_resolved_stage else resolved_stage

        if 'stage_id' in vals:
            bypass_resolved_check = self.env.context.get('bypass_resolved_check', False)

            for task in self:
                if task.is_fsm and not bypass_resolved_check:
                    current_stage = task.stage_id.id
                    new_stage = vals['stage_id']

                    if current_stage in [resolved_stage, done_stage] and \
                            new_stage not in [resolved_stage, done_stage]:
                        raise ValidationError(_(
                            "You cannot change the stage once the task is in '%s' unless it's moving to '%s' or '%s'. "
                            "Please use the 'Re-Open Task' action for other transitions."
                        ) % (
                                                  task.stage_id.display_name,
                                                  self.env['project.task.type'].browse(resolved_stage).name,
                                                  self.env['project.task.type'].browse(done_stage).name
                                              ))

        for task in self:

            previous_stage_id = task.stage_id.id

            if vals.get("stage_id") and vals["stage_id"] == resolved_stage:
                if service_resolved_stage:
                    vals["stage_id"] = done_stage

        if 'stage_id' in vals:
            in_progress_stage = self.env["project.task.type"].search(
                [("name", "=", "In Progress"), ('project_ids.is_fsm', '=', True)], limit=1)

            if vals['stage_id'] == in_progress_stage.id and not self.is_work_started:
                raise AccessError(_("You cannot move the task to 'In Progress' until you start work."))

        is_start_date_set = bool(vals.get('planned_date_begin', False))
        is_end_date_set = bool(vals.get("date_deadline", False))
        both_dates_changed = 'planned_date_begin' in vals and 'date_deadline' in vals
        self_fsm = self_fsm.with_context(fsm_mode=True)

        if self_fsm and (
                (both_dates_changed and is_start_date_set != is_end_date_set) or (not both_dates_changed and (
                ('planned_date_begin' in vals and not all(bool(t.date_deadline) == is_start_date_set for t in self)) or
                ('date_deadline' in vals and not all(bool(t.planned_date_begin) == is_end_date_set for t in self))
        ))
        ):
            vals.update({"date_deadline": False, "planned_date_begin": False})

        if 'planned_date_begin' in vals or 'date_deadline' in vals:
            vals['has_planned_date_changed'] = False

        res = super(Task, self_fsm).write(vals)

        # Handle WhatsApp notifications for stage changes
        new_stage_id = vals.get('stage_id')
        if new_stage_id and previous_stage_id != new_stage_id and task.is_fsm:
            task._send_whatsapp_on_stage_change(new_stage_id)

        return res

    # ---- Whatsapp code----

    def _send_whatsapp_on_stage_change(self, new_stage_id):
        """
        Sends WhatsApp message with attachment (if available) when a task enters a new stage.
        @param new_stage_id: ID of the new stage
        """
        self.ensure_one()

        # Get the new stage record
        new_stage = self.env['project.task.type'].browse(new_stage_id)
        if not new_stage:
            return

        # Fetch WhatsApp template for this stage
        whatsapp_template = self.env['template.whatsapp'].search([
            ('model_id.model', '=', 'project.project'),
            ('project_id', '=', self.project_id.id),
            ('stage_id', '=', new_stage_id)
        ], limit=1)

        if whatsapp_template and whatsapp_template.message:
            # ? Send WhatsApp notification using the template-defined message
            self.send_whatsapp_notification(whatsapp_template)
        else:
            print(
                f"?? No WhatsApp template with a message found for project '{self.project_id.name}', stage '{new_stage.name}'."
            )

    def get_whatsapp_configuration(self):
        """
        Fetch WhatsApp session, security key, IP, and port from configuration.manager.
        """
        config = self.env['manager.configuration'].search([], limit=1, order="id desc")
        if not config:
            print("No WhatsApp Configuration found! Please set up Configuration Manager.")
            return None  # Return None instead of raising an error
        return {
            'session': config.instance,
            'security_key': config.token,
            'ip_address': config.ip_address,
            'port': config.port
        }

    def send_whatsapp_notification(self, whatsapp_template):
        """Sends WhatsApp notification with template and attachments."""
        # Check if a call coordinator is selected and has a mobile number
        if self.call_coordinator_id and self.call_coordinator_id.mobile:
            phone_number = self.call_coordinator_id.mobile
            print(f"? Sending WhatsApp to Call Coordinator: {phone_number}")
        else:
            # Fallback to customer’s mobile number if no coordinator mobile is available
            if self.partner_id.mobile:
                phone_number = self.partner_id.mobile
                print(f"? Sending WhatsApp to Customer: {phone_number}")
            else:
                print(f"? No mobile number found for service call '{self.name}'")
                return

        # ? Clean phone number safely (handle None/False values)
        phone_number = re.sub(r'\+\d{1,3}\s*', '', str(phone_number or '')).replace(" ", "")
        print(phone_number)
        # formatted_message = whatsapp_template.message
        formatted_message = html2plaintext(whatsapp_template.message or "")

        if '{{task_name}}' in formatted_message or '{{stage_name}}' in formatted_message:
            formatted_message = formatted_message.replace('{{task_name}}', self.name or '')
            formatted_message = formatted_message.replace('{{stage_name}}', self.stage_id.name or '')

        try:
            # Fetch WhatsApp Config
            config_data = self.get_whatsapp_configuration()
            if not config_data:
                print("No WhatsApp Configuration found! Please set up Configuration Manager.")
                return  # Exit gracefully without raising an error
            base_url = f"http://{config_data['ip_address']}:{config_data['port']}/api"
            session_id = config_data['session']
            secret_key = config_data['security_key']

            # Generate Authentication Token
            token_url = f"{base_url}/{session_id}/{secret_key}/generate-token"
            token_response = requests.post(token_url)
            token_response.raise_for_status()
            token = token_response.json().get("token")

            if not token:
                print("Token generation failed: No token received")
                return

            print("? Token generated successfully!")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            # Handle attachments if present
            if whatsapp_template.attachment_ids:
                self._send_whatsapp_with_attachments(
                    base_url, session_id, headers,
                    phone_number, formatted_message,
                    whatsapp_template.attachment_ids
                )
            else:
                # Send regular message
                self._send_whatsapp_message(
                    base_url, session_id, headers,
                    phone_number, formatted_message
                )

        except requests.exceptions.RequestException as e:
            print(f"WhatsApp API error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in WhatsApp notification: {str(e)}")

    def _send_whatsapp_with_attachments(self, base_url, session_id, headers, phone_number, message, attachments):
        """Helper method to send WhatsApp message with attachments."""
        for attachment in attachments:

            try:
                attachment_sudo = attachment.sudo()
                if not attachment_sudo.datas:
                    print(f"Attachment {attachment_sudo.name} is empty or corrupted.")
                    continue
                base64_string = attachment_sudo.datas.decode('utf-8')
                file_url = f"data:{attachment_sudo.mimetype};base64,{base64_string}"

                payload = {
                    "phone": phone_number,
                    "isGroup": False,
                    "isViewOnce": False,
                    "isLid": False,
                    "fileName": attachment_sudo.name,
                    "caption": message,
                    "base64": file_url,
                    'public': True
                }

                response = requests.post(
                    f"{base_url}/{session_id}/send-file-base64",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                print(f"? WhatsApp attachment '{attachment.name}' sent successfully!")

            except requests.exceptions.RequestException as e:
                print(f"Failed to send WhatsApp attachment '{attachment.name}': {str(e)}")

    def _send_whatsapp_message(self, base_url, session_id, headers, phone_number, message):
        """Helper method to send regular WhatsApp message."""
        payload = {
            "phone": phone_number,
            "isGroup": False,
            "isNewsletter": False,
            "isLid": False,
            "message": message,
            "sanitize": False
        }

        response = requests.post(
            f"{base_url}/{session_id}/send-message",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        print("? WhatsApp message sent successfully!")

    # ---- Whatsapp code----

    @api.model
    def _group_expand_project_ids(self, projects, domain, order):
        res = super()._group_expand_project_ids(projects, domain, order)
        if self._context.get('fsm_mode'):
            search_on_comodel = self._search_on_comodel(domain, "project_id", "project.project", order,
                                                        [('is_fsm', '=', True)])
            res &= search_on_comodel
        return res

    @api.model
    def _group_expand_user_ids(self, users, domain, order):
        res = super()._group_expand_user_ids(users, domain, order)
        if self.env.context.get('fsm_mode'):
            recently_created_tasks_user_ids = self.env['project.task']._read_group([
                ('create_date', '>', datetime.now() - timedelta(days=30)),
                ('is_fsm', '=', True),
                ('user_ids', '!=', False)
            ], [], ['user_ids:array_agg'])[0][0]
            search_domain = ['&', ('company_id', 'in', self.env.companies.ids), '|', '|', ('id', 'in', users.ids),
                             ('groups_id', 'in', self.env.ref('industry_fsm.group_fsm_user').id),
                             ('id', 'in', recently_created_tasks_user_ids)]
            res |= users.search(search_domain, order=order)
        return res

    def _compute_fsm_done(self):
        closed_tasks = self.filtered(lambda t: t.state in CLOSED_STATES)
        closed_tasks.fsm_done = True

    def action_timer_start(self):
        if not self.user_timer_id.timer_start and self.display_timesheet_timer:
            super(Task, self).action_timer_start()
            if self.is_fsm:
                time = fields.Datetime.context_timestamp(self, self.timer_start)
                self.message_post(
                    body=_(
                        'Timer started at: %(date)s %(time)s',
                        date=time.strftime(get_lang(self.env).date_format),
                        time=time.strftime(get_lang(self.env).time_format),
                    ),
                )

    def action_view_timesheets(self):
        kanban_view = self.env.ref('hr_timesheet.view_kanban_account_analytic_line')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time'),
            'res_model': 'account.analytic.line',
            'view_mode': 'kanban',
            'views': [(kanban_view.id, 'kanban')],
            'domain': [('task_id', '=', self.id), ('project_id', '!=', False)],
            'context': {
                'fsm_mode': True,
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            }
        }

    def action_fsm_validate(self, stop_running_timers=False):
        """ Moves Task to done state.
            If allow billable on task, timesheet product set on project and user has privileges :
            Create SO confirmed with time and material.
        """
        if not self.env.user.has_group('industry_fsm.group_fsm_supervisor'):
            raise AccessError(_('Only admin can click the "Re-open" button. You are not authorized.'))
        self.ensure_one()
        resolved_stage = self.env['project.task.type'].search([
            ('name', '=', 'Resolved'),
            ('project_ids.is_fsm', '=', True)
        ], limit=1)
        done_stage = self.env['project.task.type'].search([
            ('name', '=', 'Done'),
            ('project_ids.is_fsm', '=', True)
        ], limit=1)
        valid_stages = done_stage | resolved_stage
        if self.stage_id not in valid_stages:
            raise ValidationError(_('You can only re-open a task when it is in "Done" or "Resolved" stage.'))

        return {
            'name': 'Re-Open Task',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task.reopen.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'bypass_resolved_check': True,

            }
        }

    def action_view_reopen_logs(self):

        return {
            'name': 'Re-Open Logs',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'project.task.reopen.log',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }

    def action_view_customer_complaint_log(self):
        self.ensure_one()
        matching_tasks = self.env['project.task'].search([
            ('partner_id', '=', self.partner_id.id),
            ('is_fsm', '=', True),
            ('parent_id', '=', False),
            ('id', '!=', self.id),
        ])

        matching_task_ids = matching_tasks.ids
        return {
            'name': 'Customer-Call Logs',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'project.task',
            'views': [
                (self.env.ref('industry_fsm.project_task_view_list_fsm').id, 'tree'),
                (False, 'form'),
            ],
            'domain': [
                ('id', 'in', matching_task_ids),
            ],
            'context': {'default_task_id': self.id, 'create': False},
        }

    def unlink(self):
        """Check delete permissions for supervisors"""
        for task in self:
            if task.is_fsm and task.department_id and \
                    self.env.user.has_group('industry_fsm.group_fsm_supervisor') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_manager') and \
                    self.env.user.id not in task.user_ids.ids:

                # Check allowed departments
                allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('unlink')
                if task.department_id.id not in allowed_dept_ids:
                    raise AccessError(_(
                        "You do not have delete access for tasks in department '%s'.") % task.department_id.name)

        for record in self:
            if record.is_fsm:
                if not self.env.user.has_group("industry_fsm.group_fsm_supervisor"):
                    raise AccessError("You do not have permission to delete this record.")
        return super(Task, self).unlink()

    @api.model
    def _stop_all_timers_and_create_timesheets(self, tasks_running_timer_ids, timesheets_running_timer_ids, timesheets):
        ConfigParameter = self.env['ir.config_parameter'].sudo()
        Timesheet = self.env['account.analytic.line']

        if not tasks_running_timer_ids and not timesheets_running_timer_ids:
            return Timesheet

        result = Timesheet
        minimum_duration = int(ConfigParameter.get_param('timesheet_grid.timesheet_min_duration', 0))
        rounding = int(ConfigParameter.get_param('timesheet_grid.timesheet_rounding', 0))
        if tasks_running_timer_ids:
            task_dict = {task.id: task for task in self}
            timesheets_vals = []
            for timer in tasks_running_timer_ids:
                minutes_spent = timer._get_minutes_spent()
                time_spent = self._timer_rounding(minutes_spent, minimum_duration, rounding) / 60
                task = task_dict[timer.res_id]
                timesheets_vals.append({
                    'task_id': task.id,
                    'project_id': task.project_id.id,
                    'user_id': timer.user_id.id,
                    'unit_amount': time_spent,
                })
            tasks_running_timer_ids.sudo().unlink()
            tasks_running_timer_ids.sudo().unlink()
            result += Timesheet.sudo().create(timesheets_vals)

        if timesheets_running_timer_ids:
            timesheets_dict = {timesheet.id: timesheet for timesheet in timesheets}
            for timer in timesheets_running_timer_ids:
                timesheet = timesheets_dict[timer.res_id]
                minutes_spent = timer._get_minutes_spent()
                timesheet._add_timesheet_time(minutes_spent)
                result += timesheet
            timesheets_running_timer_ids.sudo().unlink()

        return result

    def action_fsm_navigate(self):
        if not self.partner_id.city or not self.partner_id.country_id:
            return {
                'name': _('Customer'),
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'view_id': self.env.ref('industry_fsm.view_partner_address_form_industry_fsm').id,
                'target': 'new',
            }
        return self.partner_id.action_partner_navigate()

    def web_read(self, specification: Dict[str, Dict]) -> List[Dict]:
        if len(self) == 1 and 'partner_id' in specification and 'show_address_if_fsm' in specification[
            'partner_id'].get('context', {}):
            specification['partner_id']['context']['show_address'] = self.is_fsm
        return super().web_read(specification)

    # ---------------------------------------------------------
    # Business Methods
    # ---------------------------------------------------------

    def _get_projects_to_make_billable_domain(self, additional_domain=None):
        return expression.AND([
            super()._get_projects_to_make_billable_domain(additional_domain),
            [('is_fsm', '=', False)],
        ])

    # --------------------------------------------------------------
    # Access Rights Methods for supervisor

    def check_department_permission(self, operation):
        """Check if current user has permission for operation on this task's department"""
        # Skip checks for admins, own tasks, tasks without departments, and non-FSM tasks
        if not self.env.user.has_group('industry_fsm.group_fsm_supervisor') or \
                self.env.user.has_group('industry_fsm.group_fsm_manager') or \
                self.env.user.id in self.user_ids.ids or \
                not self.is_fsm or not self.department_id:
            return True

        # Get user's employee record
        employee = self.env.user.employee_id
        if not employee:
            raise AccessError(_("Your user is not linked to an employee."))

        # Allow access to tasks in user's own department if no permissions defined
        if employee.department_id and employee.department_id.id == self.department_id.id:
            return True

        # Check department permission
        allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids(operation)
        if self.department_id.id not in allowed_dept_ids:
            raise AccessError(_(
                "You do not have %s access to tasks in department '%s'.") %
                              (operation, self.department_id.name))

        return True

    def _search(self, args, offset=0, limit=None, order=None, access_rights_uid=None):
        """Override _search to enforce department-based visibility for FSM tasks"""
        if self._context.get('fsm_mode'):
            # Handle FSM user role (non-supervisor, non-admin)
            if self.env.user.has_group('industry_fsm.group_fsm_user') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_supervisor') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_manager'):
                # Regular users can only see tasks assigned to them
                fsm_user_domain = [
                    '|',
                    ('is_fsm', '=', False),  # Non-FSM tasks follow regular project access rules
                    '&',
                    ('is_fsm', '=', True),
                    ('user_ids', 'in', self.env.user.id)  # Only show FSM tasks assigned to this user
                ]

                # Add user restriction to args
                user_args = []
                for arg in args:
                    user_args.append(arg)
                user_args.extend(fsm_user_domain)
                args = user_args

            # Handle FSM supervisor role
            elif self.env.user.has_group('industry_fsm.group_fsm_supervisor') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_manager'):
                # Get allowed departments
                allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('read')
                employee = self.env.user.employee_id

                # Create domain for visibility restrictions
                fsm_domain = [
                    ('is_fsm', '=', True),
                    '|',
                    ('user_ids', 'in', self.env.user.id),  # User's own tasks
                    '|',
                    ('department_id', 'in', allowed_dept_ids),  # Departments with explicit permission
                    '|',
                    ('department_id', '=', False),  # Tasks with no department
                    ('department_id', '=', employee.department_id.id if employee and employee.department_id else -1)
                    # User's department
                ]

                # Add FSM specific domain to args
                fsm_args = []
                for arg in args:
                    fsm_args.append(arg)
                fsm_args.extend(['|', ('is_fsm', '=', False)] + fsm_domain)
                args = fsm_args

        return super(Task, self)._search(args, offset=offset, limit=limit, order=order,
                                         access_rights_uid=access_rights_uid)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to enforce task visibility for all user types"""
        if self._context.get('fsm_mode'):
            # Handle FSM user role (non-supervisor, non-admin)
            if self.env.user.has_group('industry_fsm.group_fsm_user') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_supervisor') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_manager'):
                # Regular users can only see tasks assigned to them
                domain = domain or []
                domain = ['|',
                          ('is_fsm', '=', False),  # Non-FSM tasks follow regular project access rules
                          '&',
                          ('is_fsm', '=', True),
                          ('user_ids', 'in', self.env.user.id)  # Only show FSM tasks assigned to this user
                          ] + domain

            # Handle FSM supervisor role
            elif self.env.user.has_group('industry_fsm.group_fsm_supervisor') and not self.env.user.has_group(
                    'industry_fsm.group_fsm_manager'):
                allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('read')
                employee = self.env.user.employee_id

                fsm_domain = [
                    ('is_fsm', '=', True),
                    '|',
                    ('user_ids', 'in', self.env.user.id),
                    '|',
                    ('department_id', 'in', allowed_dept_ids),
                    '|',
                    ('department_id', '=', False),
                    ('department_id', '=', employee.department_id.id if employee and employee.department_id else -1)
                ]

                # Combine with existing domain
                domain = domain or []
                domain = ['|', ('is_fsm', '=', False)] + fsm_domain + domain

        return super(Task, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    def read(self, fields=None, load='_classic_read'):
        """Override read to enforce task visibility for all user types"""
        records = super(Task, self).read(fields=fields, load=load)
        if self._context.get('fsm_mode'):
            # Handle FSM user role (non-supervisor, non-admin)
            if self.env.user.has_group('industry_fsm.group_fsm_user') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_supervisor') and \
                    not self.env.user.has_group('industry_fsm.group_fsm_manager'):
                filtered_records = []
                for record in records:
                    task = self.browse(record['id'])
                    # Skip if not FSM task
                    if not task.is_fsm:
                        filtered_records.append(record)
                        continue

                    # Only allow access to tasks assigned to this user
                    if self.env.user.id in task.user_ids.ids:
                        filtered_records.append(record)

                return filtered_records

            # Handle FSM supervisor role
            elif self.env.user.has_group('industry_fsm.group_fsm_supervisor') and not self.env.user.has_group(
                    'industry_fsm.group_fsm_manager'):
                allowed_dept_ids = self.env['call.visibility'].get_allowed_department_ids('read')
                employee = self.env.user.employee_id
                own_dept_id = employee.department_id.id if employee and employee.department_id else False

                # Filter records
                filtered_records = []
                for record in records:
                    task = self.browse(record['id'])
                    # Skip if not FSM task
                    if not task.is_fsm:
                        filtered_records.append(record)
                        continue

                    # Always allow access to own tasks
                    if self.env.user.id in task.user_ids.ids:
                        filtered_records.append(record)
                        continue

                    # Check department access
                    dept_id = task.department_id.id if task.department_id else False
                    if not dept_id:
                        filtered_records.append(record)
                    elif dept_id in allowed_dept_ids or dept_id == own_dept_id:
                        filtered_records.append(record)

                return filtered_records

        return records

    # --------------------------------------------------------------
    # ------------------------------------------------------------------------

    dynamic_info = fields.Html(string="Extra Info")

    def _get_call_dynamic_field_values(self):
        dynamic_fields = self.env['dynamic.fields'].search([
            ('model_id.model', '=', self._name), ('invisible_type', '=', 'task')
        ])
        result = []
        for df in dynamic_fields:
            field_name = df.name
            if field_name in self._fields:
                result.append({
                    "label": df.field_description,
                    "value": self[field_name] or "",
                })
        return result

    # dynamic_fields = fields.Text(
    #     string="Dynamic Fields (JSON)",
    #     help="Stores dynamically added fields in JSON format."
    # )
    #
    # dynamic_fields_display = fields.Char(
    #     string="Extra Info",
    #     compute="_compute_dynamic_fields_display",
    #     store=True,
    # )
    #
    # @api.depends("dynamic_fields")
    # def _compute_dynamic_fields_display(self):
    #     ignored_fields = {"create_date", "create_uid", "id", "write_date", "write_uid"}
    #
    #     for task in self:
    #         if task.dynamic_fields:
    #             try:
    #                 dynamic_data = json.loads(task.dynamic_fields)
    #
    #                 # Remove ignored fields
    #                 filtered_data = {
    #                     key: value for key, value in dynamic_data.items()
    #                     if key not in ignored_fields
    #                 }
    #
    #                 # Remove ignored fields from existing display data
    #                 existing_data = {}
    #                 if task.dynamic_fields_display:
    #                     for line in task.dynamic_fields_display.split("\n"):
    #                         key_value = line.split(": ", 1)
    #                         if len(key_value) == 2:
    #                             key, value = key_value
    #                             if key not in ignored_fields:
    #                                 existing_data[key] = value
    #
    #                 # Merge new values with existing ones
    #                 for key, value in filtered_data.items():
    #                     if key in existing_data:
    #                         existing_data[key] += f", {value}"  # Concatenate values
    #                     else:
    #                         existing_data[key] = value
    #
    #                 # Format final output
    #                 task.dynamic_fields_display = "\n".join(
    #                     f"{key}: {value}" for key, value in existing_data.items()
    #                 )
    #
    #             except json.JSONDecodeError:
    #                 task.dynamic_fields_display = "Invalid JSON format"
    #         else:
    #             task.dynamic_fields_display = ""

    def action_start_service_call_timer(self):
        """Start a timesheet timer for this call."""
        self.ensure_one()

        # Restriction: Task must have at least one assignee
        if not self.user_ids:
            raise ValidationError("This call has no assignees! Please add assignees to start work.")

        # Restriction: Only assigned users can start the timer
        if self.env.user not in self.user_ids:
            raise ValidationError("Only assigned users can start the timer.")

        # Find any running timer for the current user
        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('is_fsm', '=', True)
        ], limit=1)

        if running_timer:
            raise ValidationError(f"You already have a running timer: {running_timer.name}")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)

        # Call geofencing check for check-in
        self.env['account.analytic.line']._validate_geofence_checkin(self, latitude, longitude)

        # You should handle default category ID properly or pass it from the form
        default_category = self.env['custom.timesheet.category'].search([('code', '=', 'SERVICE_CALL')], limit=1)
        if not default_category:
            raise ValidationError("Please define at least one timesheet category.")

        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        timesheet = self.env['account.analytic.line'].create({
            'name': f'Call: {self.name}',
            'user_id': self.env.user.id,
            'task_id': self.id,
            'project_id': self.project_id.id,
            'category_id': default_category.id,
            'source_model': 'project.task',
            'source_record_id': self.id,
            'start_latitude': latitude,
            'start_longitude': longitude,
            'start_address': address,
        })

        self.write({
            "is_work_started": True,
        })

        # Fetch the "In Progress" stage and move to in progress
        in_progress_stage = self.env["project.task.type"].search(
            [("name", "=", "In Progress"), ('project_ids.is_fsm', '=', True)], limit=1)

        if in_progress_stage:
            self.stage_id = in_progress_stage.id

        self.date_time = fields.Datetime.now()

        # --- Create GPS Tracking Point (CALL START) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_start',
                address=address,
                source_model='project.task',
                source_record_id=self.id,
            )

        return timesheet.action_start_timer()

    def action_open_end_service_wizard(self):
        self.ensure_one()

        # Restriction: Task must have at least one assignee
        if not self.user_ids:
            raise ValidationError("This call has no assignees! Please add assignees to stop work.")

        # Restriction: Only assigned users can start the timer
        if self.env.user not in self.user_ids:
            raise ValidationError("Only assigned users can stop the timer.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)
        return {
            'name': 'End Service Call',
            'type': 'ir.actions.act_window',
            'res_model': 'end.service.call.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                # 'default_complaint_type_id':self.complaint_type_id.ids,
                'default_latitude': latitude,
                'default_longitude': longitude,
            }
        }

    def action_stop_service_call_timer(self):
        """Stop the currently running timer for this task."""
        self.ensure_one()

        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('is_fsm', '=', True),
            ('task_id', '=', self.id),
        ], limit=1)

        if not running_timer:
            raise ValidationError("No running timer found for this service call.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)

        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        # Call geofencing check for check-out
        self.env['account.analytic.line']._validate_geofence_checkout(self, latitude, longitude)

        running_timer.write({
            'end_latitude': latitude,
            'end_longitude': longitude,
            'end_address': address,
        })

        # --- Create GPS Tracking Point (CALL END) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_end',
                address=address,
                source_model='project.task',
                source_record_id=self.id,
            )

        return running_timer.action_stop_timer()


class EndServiceCallWizard(models.TransientModel):
    _name = "end.service.call.wizard"
    _description = "Service Call End Work Wizard"

    task_id = fields.Many2one("project.task", string="Call", required=True, readonly=True)
    stage_id = fields.Many2one(
        "project.task.type",
        string="Select Stage",
        required=True,
        domain="[('name', 'in', ['Pending', 'Resolved']), ('project_ids.is_fsm', '=', True)]"
    )
    pending_reason = fields.Many2one("pending.reason", string="Pending Reason", tracking=True)
    problem_description = fields.Char(string="Actual Problem")
    fix_description = fields.Char(string="Problem Solution")
    show_pending_reason = fields.Boolean(compute="_compute_field_visibility")
    show_problem_fields = fields.Boolean(compute="_compute_field_visibility")
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    report_signature = fields.Binary('Signature', copy=False, attachment=True)
    report_signed_by = fields.Char('Signed By', copy=False)

    # dynamic_fields_json = fields.Text(string="Dynamic Fields", help="Stores dynamically added fields")
    actual_problem = fields.Many2many(comodel_name='actual.problem', string='Actual Problems')

    # complaint_type_id = fields.Many2many("complaint.type", string="Complaint Type", readonly=True)

    @api.depends("stage_id")
    def _compute_field_visibility(self):
        """ Controls field visibility based on selected stage. """
        for record in self:
            record.show_pending_reason = record.stage_id.name == "Pending"
            record.show_problem_fields = record.stage_id.name == "Resolved"
        # self.get_view()

    def _get_dynamic_field_values(self):
        dynamic_fields = self.env['dynamic.fields'].search([
            ('model_id.model', '=', self._name)
        ])
        result = []
        for df in dynamic_fields:
            field_name = df.name
            if field_name in self._fields:
                result.append({
                    "label": df.field_description,
                    "value": self[field_name] or "",
                })
        return result

    # @api.model
    # def get_view(self, view_id=None, view_type="form", **options):
    #     res = super().get_view(view_id=view_id, view_type=view_type, **options)
    #
    #     if view_type == "form":
    #         complaint_type_id = None
    #
    #         # Try from context
    #         if self.env.context.get("default_complaint_type_id"):
    #             complaint_type_id = self.env.context["default_complaint_type_id"]
    #
    #         # Try from task if passed
    #         elif self.env.context.get("default_task_id"):
    #             task = self.env["project.task"].browse(self.env.context["default_task_id"])
    #             complaint_type_id = task.complaint_type_id.id
    #
    #         # else:
    #         #     complaint_type_id = 1
    #         print("➡ complaint_type_id in get_view:", complaint_type_id)
    #
    #         from lxml import etree
    #         if complaint_type_id:
    #             complaint_type = self.env["complaint.type"].browse(complaint_type_id)
    #             allowed_fields = complaint_type.custom_field.mapped("name")
    #             print("✅ Complaint Type:", complaint_type.display_name)
    #             print("✅ Allowed dynamic fields:", allowed_fields)
    #
    #             doc = etree.XML(res["arch"])
    #             for node in doc.xpath("//field"):
    #                 field_name = node.get("name")
    #                 if not field_name:
    #                     continue
    #
    #                 print(f"🔎 Checking field: {field_name}")
    #                 if field_name.startswith("x_") and field_name not in allowed_fields:
    #                     print(f"❌ Removing field: {field_name} (not in allowed)")
    #                     node.getparent().remove(node)
    #                 else:
    #                     print(f"✔ Keeping field: {field_name}")
    #
    #             res["arch"] = etree.tostring(doc, encoding="unicode")
    #         else:
    #             print("⚠️ No complaint_type_id in context → skipping filtering")
    #
    #     return res

    def action_end_work(self):
        """ Stops work and updates the task details, including stage change and dynamic fields. """
        self.ensure_one()

        if not self.task_id:
            raise ValidationError(_("No call found. Please reopen the wizard from a call record."))

        # Fetch the latest timesheet entry
        start_entry = self.env["account.analytic.line"].search([
            ("task_id", "=", self.task_id.id),
            ("is_timer_running", "=", True)  # Ensure it matches the start entry
        ], order="id desc", limit=1)

        if not start_entry:
            raise ValidationError(_("No 'Work Started' entry found in analytic lines."))

        # ignored_fields = {"create_date", "create_uid", "id", "write_date", "write_uid"}

        # Fetch dynamically created fields
        # dynamic_fields = self.env['ir.model.fields'].search([
        #     ('model', '=', 'end.service.call.wizard'),
        #     ('store', '=', True),
        #     ('name', 'not in', ['dynamic_fields_json', 'stage_id', 'pending_reason', 'task_id', 'problem_description',
        #                         'fix_description', 'attachment_ids', 'report_signature', 'report_signed_by']),
        # ])

        # dynamic_data = {}
        # for field in dynamic_fields:
        #     field_name = field.name
        #     field_value = getattr(self, field_name, False)
        #
        #     if field_value and field_name not in ignored_fields:
        #         if isinstance(field_value, (date, datetime)):
        #             if isinstance(field_value, (date, datetime)):
        #                 if isinstance(field_value, datetime):
        #                     field_value = field_value.strftime('%Y-%m-%d %H:%M:%S')
        #                 elif isinstance(field_value, date):
        #                     field_value = field_value.strftime('%Y-%m-%d')
        #         elif isinstance(field_value, models.Model):
        #             field_value = field_value.ids
        #         elif isinstance(field_value, list) and all(isinstance(v, models.Model) for v in field_value):
        #             field_value = [v.id for v in field_value]
        #
        #         dynamic_data[field.field_description] = field_value

        # Prepare update values
        update_values = {
            "stage_id": self.stage_id.id,
        }
        if self.stage_id.name == "Pending":
            update_values["pending_reason"] = self.pending_reason.id

        if self.stage_id.name == "Resolved":
            # Ensure required fields are filled before transitioning to "Resolved"

            prev_problem_desc = self.task_id.problem_description or ""
            prev_fix_desc = self.task_id.fix_description or ""
            prev_actual_desc = self.task_id.actual_problem or ""

            update_values["problem_description"] = (
                f"{prev_problem_desc},{self.problem_description}" if prev_problem_desc else self.problem_description
            )
            update_values["fix_description"] = (
                f"{prev_fix_desc},{self.fix_description}" if prev_fix_desc else self.fix_description
            )
            existing_ids = self.task_id.actual_problem.ids
            new_ids = self.actual_problem.ids
            merged_ids = list(set(existing_ids + new_ids))
            update_values["actual_problem"] = [(6, 0, merged_ids)]

            # Ensure at least one timesheet entry exists
            timesheet_count = self.env["account.analytic.line"].search_count([
                ("task_id", "=", self.task_id.id)
            ])

            if self.report_signature:
                self.task_id.write({
                    'report_signature': self.report_signature,
                    'report_signed_by': self.report_signed_by,
                })

                # Store Attachments in mail.thread
            for attachment in self.attachment_ids:
                attachment.copy({
                    'res_model': 'project.task',
                    'res_id': self.task_id.id,
                })

            # Required fields validation logic
            missing_fields = []

            company = self.task_id.company_id
            task = self.task_id

            # Check if attachment or signature is required
            attachment_required = False
            signature_required = False
            required_field_names = set()  # dynamic required fields from complaint or company

            if task.complaint_type_id:
                for ct in task.complaint_type_id:
                    if ct.attachment_on_out and company.attachment_required:
                        attachment_required = True
                    if ct.signed_required and company.signed_required:  # fixed key: should be `signed_on_out`
                        signature_required = True
                    if ct.resolved_required_fields:
                        required_field_names.update(ct.resolved_required_fields.mapped("name"))
            else:
                attachment_required = company.attachment_required
                signature_required = company.signed_required
                required_field_names.update(company.resolved_required_fields.mapped("name"))

            # Check attachment
            if attachment_required and not self.attachment_ids:
                missing_fields.append(_("Attachment"))

            # Check signature
            if signature_required and not self.report_signature:
                missing_fields.append(_("Signature"))

            # Wizard-editable fields

            # wizard_editable_fields = ['problem_description', 'fix_description', 'report_signed_by']
            wizard_editable_fields = list(self.env['end.service.call.wizard']._fields.keys())

            # Validate dynamically required fields
            for field_name in required_field_names:
                if field_name in wizard_editable_fields:
                    value = getattr(self, field_name, None)
                else:
                    value = getattr(task, field_name, None)
                if not value:
                    field_obj = task._fields.get(field_name) or self._fields.get(field_name)
                    field_label = field_obj.string if field_obj else field_name
                    missing_fields.append(field_label)

            # Final error raise
            if missing_fields:
                raise ValidationError(
                    _("The following fields are required to resolve this task:\n- %s") % "\n- ".join(missing_fields)
                )

            # new code for require
            if timesheet_count == 0:
                raise ValidationError(_("You must have at least one timesheet entry to move to Resolved."))

        # Merge with existing dynamic fields
        # if dynamic_data:
        #     # Load existing JSON data
        #     existing_dynamic_data = json.loads(self.task_id.dynamic_fields or '{}')
        #
        #     # Remove problem_description and fix_description if they exist
        #     existing_dynamic_data.pop("Problem Description", None)
        #     existing_dynamic_data.pop("Fix Description", None)
        #
        #     # Merge only the required dynamic data
        #     existing_dynamic_data.update(dynamic_data)
        #
        #     update_values['dynamic_fields'] = json.dumps(existing_dynamic_data)

        # Update the task record
        self.task_id.write(update_values)

        """Push custom fields values into Extra info"""
        for rec in self:
            values = rec._get_dynamic_field_values()
            call_value = rec.task_id._get_call_dynamic_field_values()
            if not values and not call_value:
                rec.task_id.dynamic_info = ""
                continue

            # Combine all values into one list
            all_values = []
            if call_value:
                all_values.extend(call_value)
            if values:
                all_values.extend(values)

            info_html = """
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Custom Fields</th>
                        <th style="padding:6px; text-align:left;">Value</th>
                    </tr>
                </thead>
                <tbody>
            """

            # Data rows
            for item in all_values:
                info_html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600; width:30%;">{item['label']}</td>
                        <td style="padding:6px; width:70%;">{item['value']}</td>
                    </tr>
                """

            info_html += """
                </tbody>
            </table>
            """

            self.task_id.dynamic_info = info_html
            rec.task_id.message_post(
                body=Markup(f"""
                    <div>
                        <p><b>Extra Info updated values:</b></p>
                        {info_html}
                    </div>
                """),
                subtype_xmlid="mail.mt_note"
            )

        # Stop the running timer after work completion
        self.task_id.action_stop_service_call_timer()

        return {"type": "ir.actions.act_window_close"}

    @api.onchange('actual_problem')
    def _onchange_actual_problem(self):
        if not self.problem_description:
            self.problem_description = ''

        current_desc = self.problem_description.strip()

        # Check if each actual_problem name is already in the text (loose match)
        for name in self.actual_problem.mapped('name'):
            if name not in current_desc:
                # Append with comma if needed
                if current_desc and not current_desc.endswith(','):
                    self.problem_description += ', '
                self.problem_description += name
