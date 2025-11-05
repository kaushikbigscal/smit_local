from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class LeadType(models.Model):
    _name = 'lead.type'
    _description = 'Lead Type'
    _order = 'name'

    name = fields.Char(string="Lead Type", required=True)
    code = fields.Char(
        string="Technical Key",
        copy=False,
        index=True,
        help="Stable key used internally, not shown to users"
    )
    is_system_defined = fields.Boolean(string="System Defined", default=False)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The technical name must be unique.'),
    ]

    @api.model
    def create(self, vals):
        if not vals.get("code"):
            vals["code"] = vals["name"].lower().replace(" ", "_")
        return super().create(vals)

    # @api.model
    # def get_unit_status_selection(self):
    #     """
    #     Build dynamic selection values from LeadType
    #     Returns a list of tuples: [(technical_value, display_name)]
    #     """
    #     return [(ct.code, ct.name) for ct in self.search([])]

    # def write(self, vals):
    #     # prevent changing the stable code if needed
    #     if "code" in vals:
    #         raise UserError(_("You cannot change the technical key."))
    #     for record in self:
    #         if record.is_system_defined:
    #             raise UserError(_("System-defined call types cannot be editable."))
    #     return super().write(vals)
    #
    # def unlink(self):
    #     for record in self:
    #         if record.is_system_defined:
    #             raise UserError(_("System-defined call types cannot be deleted."))
    #         task_count = self.env['project.task'].search_count(
    #             [('is_fsm', '=', True), ('call_type', '=', record.id)])
    #         if task_count > 0:
    #             raise UserError(_("This call type is used and cannot be deleted."))
    #     return super().unlink()