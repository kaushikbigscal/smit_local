from odoo import models, fields, api


class ZoneMaster(models.Model):
    _name = 'zone.master'
    _description = 'Zone Master'
    _rec_name = 'name'

    name = fields.Char(string='Zone Name', required=True)
    zone_code_ids = fields.One2many('sub.zone', 'zone_master_id')


class ReasonCode(models.Model):
    _name = 'sub.zone'
    _description = 'Sub Zone'

    name = fields.Char(string='Sub-Zone', required=True)
    zone_master_id = fields.Many2one('zone.master', ondelete='cascade')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('name', 'zone_master_id.name')
    def _compute_display_name(self):
        for record in self:
            if record.zone_master_id:
                record.display_name = f"{record.zone_master_id.name} / {record.name}"
            else:
                record.display_name = record.name

    def name_get(self):
        """Custom name display for better UX"""
        result = []
        for record in self:
            name = record.display_name or record.name
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None, name_get_uid=None):
        """Enhanced search to include zone names"""
        args = args or []
        domain = args.copy()
        if name:
            # Create search domain using | (OR) operator
            search_domain = ['|', ('name', operator, name), ('zone_master_id.name', operator, name)]
            domain = search_domain + domain
        return self._search(domain, limit=limit, order=order, access_rights_uid=name_get_uid)
