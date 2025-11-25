from odoo import models, fields, api


class Department(models.Model):
    _name = 'department.service'
    _description = 'Changes Department'
    _rec_name = 'department_id'

    department_id = fields.Many2one(
        'hr.department', string="Department",
        domain=lambda self: self._get_department_domain(),
        tracking=True
    )
    country_id = fields.Many2one('res.country', string="Country")
    state_id = fields.Many2many("res.country.state", string='State', ondelete='restrict', required=True
                                , domain="[('country_id', '=?', country_id)]")

    city_id = fields.Many2many(
        'res.city', string="City", ondelete="restrict"
    )

    city_domain = fields.Char(
        compute='_compute_city_domain',
        store=False
    )

    @api.depends('state_id')
    def _compute_city_domain(self):
        for rec in self:
            domain = []
            if rec.state_id:
                state_ids = rec.state_id.ids
                domain = [('state_id', 'in', state_ids)]
            rec.city_domain = str(domain)

    @api.model
    def _get_department_domain(self):
        """Restrict available departments to only sub-departments of 'Service Division'."""
        parent_department = self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
        return [('parent_id', '=', parent_department.id)] if parent_department else []
