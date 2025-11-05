from odoo import models, fields, api


class TimesheetCategory(models.Model):
    _name = 'custom.timesheet.category'
    _description = 'Timesheet Category'
    _order = 'name'

    name = fields.Char(
        string='Category Name',
        required=True
    )

    code = fields.Char(
        string='Code',
        required=True,
        help='Technical code for the category (e.g., CRM, PROJECT, FIELD_SERVICE)'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Related module information
    module_name = fields.Char(
        string='Related Module',
        help='Technical name of the related module'
    )

    model_names = fields.Text(
        string='Related Models',
        help='Comma-separated list of model names this category applies to'
    )

    entry_count = fields.Integer(
        string='Entry Count',
        compute='_compute_entry_count'
    )

    @api.depends()
    def _compute_entry_count(self):
        for record in self:
            record.entry_count = self.env['account.analytic.line'].search_count([
                ('category_id', '=', record.id)
            ])

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Category code must be unique!'),
    ]
