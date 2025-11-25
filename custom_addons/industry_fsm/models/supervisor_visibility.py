# call_visibility.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import ormcache


class CallVisibility(models.Model):
    _name = 'call.visibility'
    _description = 'Service Call Visibility'
    _rec_name = 'department_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one(
        'hr.department', string="Department",
        domain=lambda self: self._get_department_domain(),
        tracking=True, required=True, index=True
    )

    employee_id = fields.Many2many(
        'hr.employee', string='Supervisor',
        tracking=True,
        domain="[('user_id.groups_id', 'in', supervisor_group), "
               "('user_id.groups_id', 'not in', admin_group)]",
        required=True, index=True
    )

    supervisor_group = fields.Many2one('res.groups',
                                       default=lambda self: self.env.ref('industry_fsm.group_fsm_supervisor').id,
                                       store=False)
    admin_group = fields.Many2one('res.groups',
                                  default=lambda self: self.env.ref('industry_fsm.group_fsm_manager').id,
                                  store=False)

    perm_read = fields.Boolean(string='Read', default=True)
    perm_write = fields.Boolean(string='Write', default=False)
    perm_create = fields.Boolean(string='Create', default=False)
    perm_unlink = fields.Boolean(string='Delete', default=False)

    @api.model
    def _get_department_domain(self):
        """Restrict available departments to only sub-departments of 'Service Division'."""
        parent_department = self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
        return [('parent_id', '=', parent_department.id)] if parent_department else []

    @api.model
    @ormcache('operation', 'user_id')
    def get_allowed_department_ids(self, operation='read', user_id=None):
        """Get department IDs where specified user has permission.
        If no permissions found, return the user's own department."""
        user = self.env.user if user_id is None else self.env['res.users'].browse(user_id)

        # Admin has access to everything
        if user.has_group('industry_fsm.group_fsm_manager'):
            return self.env['hr.department'].search([]).ids

        # Not a supervisor, no department-based access
        if not user.has_group('industry_fsm.group_fsm_supervisor'):
            return []

        # Get the employee record
        employee = user.employee_id
        if not employee:
            return []

        # Find departments with specified permission
        domain = [('employee_id', 'in', [employee.id])]
        if operation == 'read':
            domain.append(('perm_read', '=', True))
        elif operation == 'write':
            domain.append(('perm_write', '=', True))
        elif operation == 'create':
            domain.append(('perm_create', '=', True))
        elif operation == 'unlink':
            domain.append(('perm_unlink', '=', True))

        records = self.search(domain)
        dept_ids = records.mapped('department_id').ids

        # If no departments found, use supervisor's own department
        if not dept_ids and employee.department_id:
            dept_ids = [employee.department_id.id]

        return dept_ids

    def clear_department_cache(self):
        """Clear the department permission cache when permissions change"""
        self.get_allowed_department_ids.cache_clear()

    @api.model_create_multi
    def create(self, vals_list):
        res = super(CallVisibility, self).create(vals_list)
        # self.clear_department_cache()
        for vals in vals_list:
            if not vals['perm_read']:
                raise ValidationError(_("You must give read rights to the selected supervisor."))
        return res

    def write(self, vals):
        res = super(CallVisibility, self).write(vals)
        # self.clear_department_cache()
        for rec in self:
            if not rec.perm_read:
                raise ValidationError(_("You must give read rights to the selected supervisor."))
        return res

    def unlink(self):
        res = super(CallVisibility, self).unlink()
        # self.clear_department_cache()
        return res
