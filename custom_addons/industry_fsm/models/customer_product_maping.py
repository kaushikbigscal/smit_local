from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import io
import base64
import xlsxwriter


# @api.model
# def _get_unit_status(self):
#     """
#     Build dynamic selection values from CallType
#     Returns a list of tuples: [(technical_value, display_name)]
#     """
#     call_types = self.env['call.type'].search([])
#     return [(ct.name.lower().replace(" ", "_"), ct.name) for ct in call_types]


class CustomerProductMapping(models.Model):
    _name = "customer.product.mapping"
    _description = "Customer Product Mapping"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = "display_name"  # Optional custom field (see below)
    active = fields.Boolean(default=True)

    description = fields.Html(string='Description')

    attachment_ids = fields.Many2many(
        'ir.attachment', 'product_mapping_ir_attachments_rel',
        'mapping_id', 'attachment_id',
        string='Attachments',
        domain=[('res_model', '=', 'customer.product.mapping')],
        context={'default_res_model': 'customer.product.mapping'},
    )

    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.onchange('start_date')
    def _onchange_set_end_date(self):
        for rec in self:
            if rec.start_date:
                # today = fields.Date.today()
                if rec.status == 'amc':
                    rec.end_date = rec.start_date + timedelta(days=365)
                elif rec.status in ['free', 'chargeable']:
                    rec.end_date = rec.start_date + timedelta(days=1)
                elif rec.status == 'warranty':
                    if rec.product_id.product_tmpl_id.is_warranty:
                        warranty_period_months = rec.product_id.product_tmpl_id.minimum_warranty_period or 0
                        rec.end_date = rec.start_date + timedelta(days=30 * warranty_period_months)
                else:
                    rec.end_date = rec.start_date + timedelta(days=1)

    @api.depends('serial_number_ids', 'product_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.serial_number_ids.name} - {rec.product_id.display_name}"

    source_type = fields.Selection([
        ('sale_order', 'From Sale Order'),
        ('direct_product', 'Direct Product'),
        ('amc', 'From AMC Contract'),
    ], string='Source Type', required=True, default='direct_product', tracking=True)

    @api.onchange('source_type')
    def _onchange_source_type(self):
        if self.source_type == 'direct_product':
            # self.order_id = False
            if not self.env.context.get('default_customer_id'):
                self.customer_id = False
            self.product_id = False
            self.serial_number_ids = False
            self.product_category = False

            # No sale order line for direct products
        elif self.source_type == 'sale_order':
            self.serial_number_ids = False
            if not self.env.context.get('default_customer_id'):
                self.customer_id = False
            self.product_id = False
            self.product_category = False

    unique_number = fields.Char(
        string='Unique Number', help="Unique Identifier", tracking=True,
    )

    customer_id = fields.Many2one(
        'res.partner', string='Customer Name', required=True, tracking=True, ondelete='cascade',
        domain="[('parent_id', '=', False)]",
    )

    product_id = fields.Many2one(
        'product.product', string='Product Name',
        domain="[('id', 'in', available_product_ids)]", ondelete='cascade',
        required=True, tracking=True,

    )
    order_id = fields.Many2one(
        'sale.order.line', ondelete='cascade', string='Order ID', readonly=False, tracking=True,
        domain="[('order_partner_id', '=', customer_id), ('product_id', '=', product_id)]"
    )

    # status = fields.Selection([
    #     ('amc', 'AMC'), ('chargeable', 'Chargeable'), ('free', 'Free'), ('warranty', 'Warranty')
    # ], string='Unit Status', required=True, tracking=True, default="chargeable")

    status = fields.Selection(
        selection=lambda self: self.env['call.type'].get_unit_status_selection(),
        string="Unit Status",
        required=True,
        tracking=True,
        default="chargeable",  # must match one of generated keys
    )

    start_date = fields.Date(
        string='Start Date', required=True,
        tracking=True
    )
    end_date = fields.Date(
        string='End Date', required=True, tracking=True,

    )

    @api.onchange('order_id')
    def _onchange_sale_line(self):
        if self.order_id and self.order_id.unit_status:
            self.status = self.order_id.unit_status

    @api.onchange('status')
    def _onchange_set_dates(self):
        today = fields.Date.today()

        for rec in self:
            if rec.source_type == 'direct_product':

                if rec.status == 'amc':
                    rec.start_date = today
                    rec.end_date = today + timedelta(days=365)
                elif rec.status in ['free', 'chargeable']:
                    rec.start_date = today
                    rec.end_date = today + timedelta(days=1)
                elif rec.product_id.product_tmpl_id.is_warranty:
                    rec.status = 'warranty'
                    rec.start_date = today
                    rec.end_date = today + timedelta(
                        days=30 * (rec.product_id.product_tmpl_id.minimum_warranty_period or 0))

                else:
                    rec.status = rec.status or 'chargeable'

            elif rec.source_type == 'sale_order':
                if rec.order_id:
                    sale_line = rec.order_id
                    # rec.status = rec.status

                    if rec.status == 'warranty':
                        rec.status = 'warranty'
                        rec.start_date = sale_line.order_id.warranty_start_date
                        rec.end_date = sale_line.line_warranty_end_date
                    elif rec.status == 'amc':
                        rec.status = 'amc'
                        rec.start_date = sale_line.order_id.warranty_start_date
                        rec.end_date = today + timedelta(days=365)
                    elif rec.status == 'free':
                        rec.status = 'free'
                        rec.start_date = sale_line.order_id.warranty_start_date
                        rec.end_date = today + timedelta(days=1)
                    elif rec.status == 'chargeable':
                        rec.status = 'chargeable'
                        rec.start_date = sale_line.order_id.warranty_start_date
                        rec.end_date = today + timedelta(days=1)
                    else:
                        if not rec.status:
                            rec.status = 'chargeable'

    product_category = fields.Many2one(
        'product.category', string='Product Category', tracking=True
    )

    available_product_ids = fields.Many2many(
        'product.product', compute="_compute_available_products", store=True
    )
    available_serial_numbers = fields.Many2many(
        'stock.lot', string="Available Serial Numbers",
        compute="_compute_available_serial_numbers",
        store=False
    )

    serial_number_ids = fields.Many2one(
        'stock.lot', string="Serial Numbers",
        domain="[('id', 'in', available_serial_numbers)]",
        store=True
    )

    # stock_count = fields.Integer(string='Stock Count', tracking=True)

    @api.depends('customer_id', 'source_type', 'product_category')
    def _compute_available_products(self):
        """ Fetch available products based on the selected customer and source type """
        for record in self:
            if record.source_type == 'sale_order' and record.customer_id:
                sale_lines = self.env['sale.order.line'].search([
                    ('order_id.partner_id', '=', record.customer_id.id)
                ])
                record.available_product_ids = sale_lines.mapped('product_id')
            elif record.source_type == 'direct_product' and record.product_category:
                record.available_product_ids = self.env['product.product'].search([
                    ('categ_id', '=', record.product_category.id),
                    ('detailed_type', '=', 'product')
                ])
            elif record.source_type == 'direct_product' and not record.product_category:
                record.available_product_ids = self.env['product.product'].search([
                    ('detailed_type', '=', 'product')
                ])
            else:
                record.available_product_ids = self.env['product.product'].browse([])

    # @api.depends('product_id', 'order_id', 'source_type')
    # def _compute_available_serial_numbers(self):
    #     """Compute available serial numbers from stock move lines based on the selected order line"""
    #     for rec in self:
    #         serial_numbers = self.env['stock.lot']
    #         rec.available_serial_numbers = False
    #
    #         if rec.source_type == 'direct_product':
    #             # Direct product lookup → all serials in stock for this product
    #             if rec.product_id:
    #                 serial_numbers = self.env['stock.lot'].search([
    #                     ('product_id', '=', rec.product_id.id)
    #                 ])
    #
    #         if rec.product_id and rec.order_id:
    #             sale_line = rec.order_id
    #             if sale_line.product_id != rec.product_id:
    #                 continue
    #
    #             if sale_line:
    #                 rec.product_category = rec.product_id.categ_id.id if rec.product_id.categ_id else False
    #
    #             if rec.product_id:
    #                 picking = self.env['stock.picking'].search([
    #                     ('sale_id', '=', sale_line.order_id.id)
    #                 ])
    #                 move_lines = self.env['stock.move.line'].search([
    #                     ('picking_id', 'in', picking.ids),
    #                     ('product_id', '=', rec.product_id.id),
    #                     ('lot_id', '!=', False)
    #                 ])
    #                 serial_numbers |= move_lines.mapped('lot_id')
    #
    #         rec.available_serial_numbers = serial_numbers
    #         if not rec.product_id or not rec.order_id:
    #             rec.serial_number_ids = False

    @api.depends('product_id', 'order_id', 'source_type')
    def _compute_available_serial_numbers(self):
        """Compute available serial numbers from stock move lines or direct product"""
        for rec in self:
            serial_numbers = self.env['stock.lot']

            if rec.source_type == 'direct_product' and rec.product_id:
                # Direct product lookup → all serials in stock for this product
                serial_numbers = self.env['stock.lot'].search([
                    ('product_id', '=', rec.product_id.id)
                ])

            elif rec.product_id and rec.order_id:
                sale_line = rec.order_id
                if sale_line.product_id != rec.product_id:
                    rec.available_serial_numbers = self.env['stock.lot']
                    rec.serial_number_ids = False
                    continue

                rec.product_category = rec.product_id.categ_id.id if rec.product_id.categ_id else False

                picking = self.env['stock.picking'].search([
                    ('sale_id', '=', sale_line.order_id.id)
                ])
                move_lines = self.env['stock.move.line'].search([
                    ('picking_id', 'in', picking.ids),
                    ('product_id', '=', rec.product_id.id),
                    ('lot_id', '!=', False)
                ])
                serial_numbers |= move_lines.mapped('lot_id')

            # Always assign a clean recordset
            rec.available_serial_numbers = self.env['stock.lot'].browse(serial_numbers.ids)
            if not rec.product_id:
                rec.serial_number_ids = False

    @api.model
    def create(self, vals):
        if not vals.get('status'):
            vals['status'] = 'chargeable'
        if vals.get('source_type', self.source_type) == "direct_product":
            print(f"Creating record with serial numbers: {vals.get('serial_number_ids')}")
        if vals.get('source_type') == 'sale_order':
            customer_id = vals.get('customer_id')
            order_id = vals.get('order_id')
            serial_id = vals.get('serial_number_ids')  # Now it's just an integer ID

            if customer_id and order_id and serial_id:
                existing_record = self.search([
                    ('customer_id', '=', customer_id),
                    ('order_id', '=', order_id),
                    ('serial_number_ids', '=', serial_id),
                ], limit=1)

                if existing_record:
                    raise ValidationError("A record already exists with the same customer, order, and serial number.")

        res = super(CustomerProductMapping, self).create(vals)
        if not res.unique_number:
            res.unique_number = self.env['ir.sequence'].next_by_code('customer.product.mapping') or '/'

        return res

    _sql_constraints = [
        ('unique_unique_number', 'unique(unique_number)', 'Unique Number must be unique!')
    ]

    def write(self, vals):

        if vals.get('source_type', self.source_type) == "direct_product":
            if not vals.get('product_id') and self.env.context.get('default_product_id'):
                vals['product_id'] = self.env.context['default_product_id']
            if 'status' not in vals and not self.status:
                vals['status'] = 'chargeable'
            if 'serial_number_ids' in vals and not vals['serial_number_ids']:
                print("Attempt to clear serial_number_id was blocked.")
                vals.pop('serial_number_ids')
                print(f"Updating record with serial numbers: {vals.get('serial_number_ids')}")
        return super(CustomerProductMapping, self).write(vals)

    def action_export_all_to_xlsx(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Export')

        headers = ['Unique Number', 'Product Name', 'Customer Name', 'Unit Status', 'Start Date', 'End Date',
                   'Source Type', 'Serial Numbers', 'Product Category']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)

        for row, rec in enumerate(self, start=1):
            worksheet.write(row, 0, rec.unique_number or '')
            worksheet.write(row, 1, rec.product_id.display_name or '')
            worksheet.write(row, 2, rec.customer_id.display_name or '')
            worksheet.write(row, 3, rec.status or '')
            worksheet.write(row, 4, rec.start_date.strftime('%Y-%m-%d') if rec.start_date else '')
            worksheet.write(row, 5, rec.end_date.strftime('%Y-%m-%d') if rec.end_date else '')
            worksheet.write(row, 6, rec.source_type or '')
            serials = ', '.join(rec.serial_number_ids.mapped('name')) if rec.serial_number_ids else ''
            worksheet.write(row, 7, serials)
            worksheet.write(row, 8, rec.product_category.name or '')
        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'customer_product_export.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self[0].id if self else False,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def unlink(self):
        for rec in self:

            linked_tasks = self.env['project.task'].search([('customer_product_id', '=', rec.id)])
            if linked_tasks:
                raise UserError("You cannot delete this mapping because it is linked to one or more calls.")
        return super(CustomerProductMapping, self).unlink()

    # product model and brand

    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related='product_id.product_tmpl_id', store=True)

    product_brand = fields.Char(string='Brand', compute='_compute_product_attributes', store=True)
    product_model = fields.Char(string='Model', compute='_compute_product_attributes', store=True)

    @api.depends('product_id')
    def _compute_product_attributes(self):
        for record in self:
            brand = False
            model = False

            if record.product_id and record.product_template_id:
                # Check for product variants with attributes
                for variant_attribute in record.product_id.product_template_attribute_value_ids:
                    if variant_attribute.attribute_id.name.lower() == 'brand':
                        brand = variant_attribute.name
                    elif variant_attribute.attribute_id.name.lower() == 'model':
                        model = variant_attribute.name

                # If not found in variants, check attribute lines
                if not brand or not model:
                    for attr_line in record.product_template_id.attribute_line_ids:
                        if attr_line.attribute_id.name.lower() == 'brand' and attr_line.value_ids:
                            brand = attr_line.value_ids[0].name
                        elif attr_line.attribute_id.name.lower() == 'model' and attr_line.value_ids:
                            model = attr_line.value_ids[0].name

            record.product_brand = brand
            record.product_model = model
