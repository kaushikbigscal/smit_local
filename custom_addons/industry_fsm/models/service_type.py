from odoo import models, fields, _, api
from random import randint
from odoo.exceptions import UserError, ValidationError


class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'Service Type'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Service Type', required=True)
    color = fields.Integer(string='Color', default=_get_default_color)
    bypass_geofencing_for_service_call = fields.Boolean(string="Bypass Geofencing For Service Call")
    default_in_call = fields.Boolean(string="Is Default")

    @api.constrains('default_in_call')
    def _check_only_one_default(self):
        for rec in self:
            if rec.default_in_call:
                existing_default = self.search([
                    ('default_in_call', '=', True),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing_default:
                    raise ValidationError(
                        f"Only one Service Type can be set as default.\n"
                        f"'{existing_default.name}' is already set as default."
                    )


class ServiceChargeCategory(models.Model):
    _name = 'service.charge.type'
    _description = 'Service Charge Type'
    _rec_name = 'service_charge_type'

    service_charge_type = fields.Char(string='Service Charge Type', required=True)


class CallType(models.Model):
    _name = 'call.type'
    _description = 'Call Type'
    _order = 'name'

    name = fields.Char(string="Call Type", required=True)
    code = fields.Char(
        string="Technical Key",
        required=True,
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

    @api.model
    def get_unit_status_selection(self):
        """
        Build dynamic selection values from CallType
        Returns a list of tuples: [(technical_value, display_name)]
        """
        return [(ct.code, ct.name) for ct in self.search([])]

    def write(self, vals):
        # prevent changing the stable code if needed
        if "code" in vals:
            raise UserError(_("You cannot change the technical key."))
        for record in self:
            if record.is_system_defined:
                raise UserError(_("System-defined call types cannot be editable."))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.is_system_defined:
                raise UserError(_("System-defined call types cannot be deleted."))
            task_count = self.env['project.task'].search_count(
                [('is_fsm', '=', True), ('call_type', '=', record.id)])
            if task_count > 0:
                raise UserError(_("This call type is used and cannot be deleted."))
        return super().unlink()
