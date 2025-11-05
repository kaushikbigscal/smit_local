from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class StoreCode(models.Model):
    _name = 'store.code'
    _description = 'Store Code'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Store Name", required=True)
    store_code = fields.Char(
        string="Store Code",
        copy=False,
        help="Store Code of the Store"
    )
    is_active = fields.Boolean(string="Is Active", help="Is this store still active?", default=True)
    store_contact = fields.Many2one(
        'res.partner',
        string="Store Contact",
        domain="[('is_company', '=', True)]",
        help="Select Store Contact for Address, Whatsapp No., Email Id"
    )
    store_email = fields.Char(
        "Store Email",
        compute="_compute_store_email",
        help="For Email on Lead Creation"
    )
    store_phone = fields.Char(
        "Store Phone",
        compute="_compute_store_phone",
        help="For Whatsapp Message"
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
        help="Latitude and Longitude of the Store"
    )
    store_open_time = fields.Char(
        "Store Open Time",
        help="Opening time of the store"
    )
    store_close_time = fields.Char(
        "Store Close Time",
        help="Closing time of the store"
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

    _sql_constraints = [
        ('code_uniq', 'unique(store_code)', 'The Store Code must be unique.'),
    ]
