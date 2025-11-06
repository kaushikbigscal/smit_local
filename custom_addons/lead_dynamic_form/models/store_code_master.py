from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class StoreCode(models.Model):
    _name = 'store.code'
    _description = 'Store Code'
    _order = 'store_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Store Name", required=True, tracking=True)
    store_code = fields.Char(
        string="Store Code",
        copy=False,
        help="Store Code of the Store", tracking=True
    )
    is_active = fields.Boolean(string="Is Active", help="Is this store still active?", default=True, tracking=True)
    store_contact = fields.Many2one(
        'res.partner',
        string="Store Contact",
        domain="[('is_company', '=', True)]",
        help="Select Store Contact for Address, Whatsapp No., Email Id", tracking=True
    )
    store_email = fields.Char(
        "Store Email",
        compute="_compute_store_email",
        help="For Email on Lead Creation", tracking=True
    )
    store_phone = fields.Char(
        "Store Phone",
        compute="_compute_store_phone",
        help="For Whatsapp Message", tracking=True
    )
    store_latitude = fields.Float(
        "Store Latitude",
        compute="_compute_lat_long",
        store=True,
        help="Latitude of the Store"
    )
    store_longitude = fields.Float(
        "Store Longitude",
        compute="_compute_lat_long",
        store=True,
        help="Longitude of the Store"
    )
    lat_long = fields.Char(
        "Lat/Long",
        compute="_compute_lat_long_display",
        help="Latitude and Longitude of the Store", tracking=True
    )
    store_open_time = fields.Char(
        "Store Open Time",
        help="Opening time of the store", tracking=True
    )
    store_close_time = fields.Char(
        "Store Close Time",
        help="Closing time of the store", tracking=True
    )

    store_address = fields.Char(
        string="Store Address",
        related="store_contact.contact_address_complete",
        readonly=True
    )

    @api.depends('store_contact')
    def _compute_store_email(self):
        for record in self:
            record.store_email = record.store_contact.email if record.store_contact else ''

    @api.depends('store_contact')
    def _compute_store_phone(self):
        for record in self:
            record.store_phone = record.store_contact.phone if record.store_contact else ''

    @api.depends('store_contact')
    def _compute_lat_long(self):
        for record in self:
            if record.store_contact and record.store_contact.partner_latitude and record.store_contact.partner_longitude:
                record.store_latitude = record.store_contact.partner_latitude
                record.store_longitude = record.store_contact.partner_longitude
            else:
                record.store_latitude = 0.0
                record.store_longitude = 0.0

    @api.depends('store_latitude', 'store_longitude')
    def _compute_lat_long_display(self):
        for record in self:
            if record.store_latitude and record.store_longitude:
                record.lat_long = f"{record.store_latitude}, {record.store_longitude}"
            else:
                record.lat_long = ''

    def name_get(self):
        res = []
        for rec in self:
            display = f"{rec.store_code or ''} - {rec.name}"
            res.append((rec.id, display))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        args = args or []
        domain = ['|', ('store_code', operator, name), ('name', operator, name)]
        records = self.search(domain + args, limit=limit)
        return records.name_get()

    _sql_constraints = [
        ('code_uniq', 'unique(store_code)', 'The Store Code must be unique.'),
    ]
