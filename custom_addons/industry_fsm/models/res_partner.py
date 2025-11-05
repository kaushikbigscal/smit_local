from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    remark = fields.Char(string="Remark")

    def action_partner_navigate(self):
        self.ensure_one()
        if not self.partner_latitude or not self.partner_longitude:
            self.geo_localize()
        url = "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (
            self.partner_latitude, self.partner_longitude)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    def unlink(self):
        for partner in self:
            used_in_tasks = self.env['project.task'].search([
                ('call_coordinator_id', '=', partner.id),
                ('is_fsm', '=', True)
            ])
            if used_in_tasks:
                raise ValidationError(_(
                    "You cannot delete the contact '%s' because it is used as a Call Coordinator in one or more service calls."
                ) % partner.name)
        return super().unlink()

    def action_view_customer_call_history(self):
        self.ensure_one()
        matching_tasks = self.env['project.task'].search([
            ('partner_id', '=', self.id),
            ('is_fsm', '=', True),
            ('parent_id', '=', False)
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
            'context': {'default_task_id': self.id, 'create': False, 'edit': False,
                        'group_by': 'stage_id'},
        }


class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_geofencing_on_checkin = fields.Boolean(
        string="Enable Geofencing On Check In",
        help="User must be within allowed distance to check-in."
    )
    enable_geofencing_on_checkout = fields.Boolean(
        string="Enable Geofencing On Check Out",
        help="User must be within allowed distance to check-out."
    )

    def action_reset_to_default_password(self):
        default_password = "pwd123#"
        for user in self:
            user.sudo().write({'password': default_password})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Password Reset to Default"),
                'message': _("Password Reset to Default Successfully."),
                'sticky': False,
                'type': 'success',
            }
        }

    def write(self, vals):
        for record in self:
            checkin = vals.get("enable_geofencing_on_checkin", record.enable_geofencing_on_checkin)
            checkout = vals.get("enable_geofencing_on_checkout", record.enable_geofencing_on_checkout)
            company = record.company_id

            if (checkin or checkout) and company.allowed_distance_service <= 0 and (
                    company.enable_geofencing_on_checkin or company.enable_geofencing_on_checkout):
                raise AccessError(_("Allowed distance must be configured in company settings."))

        return super().write(vals)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        context = self._context or {}
        args = args or []

        fsm_mode = context.get('fsm_mode', False)

        if fsm_mode:
            # Add name-based search to the domain
            if name:
                args += ['|', ('name', operator, name), ('login', operator, name)]

            users = self.search(args, limit=limit)
            result = []

            # Find stages to exclude
            excluded_stages = self.env['project.task.type'].search([
                ('name', 'in', ['Done', 'Resolved', 'Cancelled', 'Pending']),
                ('project_ids.is_fsm', '=', True)
            ])

            excluded_stage_ids = excluded_stages.ids

            for user in users:
                # Count all FSM tasks assigned to the user, excluding those in Done, Resolved, Cancelled stages
                task_count = self.env['project.task'].search_count([
                    ('is_fsm', '=', True),
                    ('user_ids', 'in', user.id),
                    ('stage_id', 'not in', excluded_stage_ids),
                ])
                result.append((user.id, f"{user.name} (Pending Calls: {task_count})"))

            return result
        else:
            # Default behavior
            return super(ResUsers, self).name_search(name, args, operator, limit)

    def get_fsm_pending_calls_by_user(self, department_id=None):
        Task = self.env['project.task']
        User = self.env['res.users']
        Employee = self.env['hr.employee']
        Department = self.env['hr.department']

        # Step 1: Get FSM stages to exclude
        excluded_stages = self.env['project.task.type'].search([
            ('name', 'in', ['Done', 'Resolved', 'Cancelled', 'Pending']),
            ('project_ids.is_fsm', '=', True)
        ])
        excluded_stage_ids = excluded_stages.ids

        # Step 2: Get filtered user list (same logic as _compute_user_ids_domain)
        if department_id:
            # Use users from the selected department
            employees = Employee.search([
                ('department_id', '=', department_id),
                ('user_id', '!=', False)
            ])
        else:
            # Fallback to "Service Division" and its sub-departments
            service_div = Department.search([('name', '=', 'Service Division')], limit=1)
            sub_depts = Department.search([('id', 'child_of', service_div.id)]).ids if service_div else []
            employees = Employee.search([
                ('department_id', 'in', sub_depts),
                ('user_id', '!=', False)
            ])

        user_ids = employees.mapped('user_id').ids

        # Step 3: Count FSM tasks not in excluded stages, assigned to these users
        tasks_grouped = Task.read_group([
            ('active', '=', True),
            ('is_fsm', '=', True),
            ('user_ids', 'in', user_ids),
            ('stage_id', 'not in', excluded_stage_ids)
        ], ['user_ids'], ['user_ids'])

        # Step 4: Map user_id to count
        user_task_count = {}
        for group in tasks_grouped:
            for uid in group.get('user_ids', []):
                user_task_count[uid] = user_task_count.get(uid, 0) + group.get('user_ids_count', 0)

        # Step 5: Return list of user data with pending counts
        users = User.browse(user_ids)
        result = [{
            'user_id': user.id,
            'user_name': user.name,
            'pending_calls': user_task_count.get(user.id, 0)
        } for user in users]

        return result
