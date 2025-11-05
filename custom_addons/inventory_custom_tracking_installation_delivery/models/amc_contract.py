from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, datetime, time, date
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AmcContract(models.Model):
    _name = 'amc.contract'
    _description = 'AMC Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char(string='Contract name', tracking=True, index='trigram', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    partner_id = fields.Many2one('res.partner', string="Customer", tracking=True,
                                 domain="['&','|', ('company_id', '=?', company_id), ('company_id', '=', False),('parent_id','=',False)]",
                                 required=True)
    start_date = fields.Date(string="Start Date", tracking=True, required=True)
    end_date = fields.Date(string="End Date", tracking=True, required=True)

    phone = fields.Char(
        compute='_compute_partner_phone',
        string="Phone", store=True, copy=False, readonly=False, tracking=True
    )
    email = fields.Char(compute='_compute_partner_email', string="Email", store=True, copy=False, readonly=False,
                        tracking=True)

    available_contacts = fields.Many2many(
        'res.partner',
        compute="_compute_available_contacts",
        store=False, tracking=True
    )
    call_coordinator_id = fields.Many2one(
        'res.partner',
        string="Call Coordinator",
        domain="[('id', 'in', available_contacts), ('parent_id', '=', partner_id)]", tracking=True
    )
    call_coordinator_phone = fields.Char(
        string="Call Coordinator Phone",
        compute="_compute_call_coordinator_phone",
        store=True, copy=False, readonly=False, tracking=True
    )
    user_ids = fields.Many2many(comodel_name='res.users', string="Assigned Technician", tracking=True)

    visit_frequency = fields.Integer(string="Visit Frequency", store=True, tracking=True)
    service_address = fields.Text(string="Service Address", compute="_compute_service_address", readonly=False,
                                  tracking=True)
    billing_address = fields.Text(string="Billing Address", compute="_compute_service_address", readonly=False,
                                  tracking=True)
    contract_type = fields.Many2one(comodel_name='contract.type', string="Contract Type", tracking=True, required=True)
    stage_id = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('not_renewed', 'Not Renewed'),
    ], string='Stage', tracking=True, default='draft')
    asset_line_ids = fields.One2many('amc.contract.asset.line', 'contract_id', string="Assets")

    comment = fields.Html("Comment", tracking=True)
    attachment_line_ids = fields.One2many(
        'amc.attachment.line', 'contract_id', string='Attachments', store=True, tracking=True)
    sla_terms = fields.Many2one('sla.term', 'SLA Terms', tracking=True, help="Service Level Agreement")
    note = fields.Html(string="Terms and conditions", translate=True)
    sale_order_count = fields.Integer(string="Sale Orders", compute="_compute_sale_order_count")
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)
    visit_count = fields.Integer(string="Scheduled Visits", compute="_compute_visit_count", store=False)
    visit_ids = fields.One2many('amc.contract.visit', 'contract_id', string="Scheduled Visits")
    amc_new_estimation = fields.Boolean(
        string="Create New Estimation",
        compute='_compute_amc_new_estimation')
    customer_product_ids = fields.One2many('customer.product.mapping', 'contract_id')

    # ================== changes by smit  =========================
    invoice_ids = fields.One2many(
        'account.move', 'amc_contract_id', string="Invoices"
    )
    show_red_highlight = fields.Boolean(string="Show Red Highlight", compute="_compute_show_red_highlight", store=True)
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string="Payment Status", compute="_compute_payment_state", store=True)

    last_payment_date = fields.Date(
        string="Last Payment Date", compute="_compute_last_payment_date", store=True
    )

    @api.depends('invoice_ids.payment_state')
    def _compute_payment_state(self):
        for contract in self:
            states = contract.invoice_ids.mapped('payment_state')
            if not states:
                contract.payment_state = 'not_paid'
            elif all(state == 'paid' for state in states):
                contract.payment_state = 'paid'
            elif any(state == 'in_payment' for state in states):
                contract.payment_state = 'in_payment'
            elif any(state == 'partial' for state in states):
                contract.payment_state = 'partial'
            elif any(state == 'reversed' for state in states):
                contract.payment_state = 'reversed'
            elif any(state == 'invoicing_legacy' for state in states):
                contract.payment_state = 'invoicing_legacy'
            else:
                contract.payment_state = 'not_paid'

    @api.depends('end_date')
    def _compute_show_red_highlight(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.end_date:
                delta_days = (record.end_date - today).days
                record.show_red_highlight = delta_days <= 30  # includes past too
            else:
                record.show_red_highlight = False

    # Optimal compute for last payment date
    @api.depends('invoice_ids.payment_state', 'invoice_ids.line_ids.payment_id.date')
    def _compute_last_payment_date(self):
        for contract in self:
            last_payment_date = False

            # Get all invoices for this contract
            invoices = contract.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice')
            if not invoices:
                contract.last_payment_date = False
                continue

            # Collect all payment dates from all invoices
            payment_dates = []

            for invoice in invoices:
                # Get payment moves linked to this invoice
                payment_moves = invoice.line_ids.mapped('payment_id').filtered(lambda p: p and p.state == 'posted')

                # Add payment dates
                for payment in payment_moves:
                    if payment.date:
                        payment_dates.append(payment.date)

                # Also check reconciled payments through account.partial.reconcile
                reconciled_payments = self.env['account.partial.reconcile'].search([
                    '|', ('debit_move_id', 'in', invoice.line_ids.ids),
                    ('credit_move_id', 'in', invoice.line_ids.ids)
                ])

                for reconcile in reconciled_payments:
                    # Get the payment move from reconciliation
                    payment_move = reconcile.debit_move_id.move_id if reconcile.debit_move_id.move_id != invoice else reconcile.credit_move_id.move_id
                    if payment_move and payment_move.move_type == 'entry' and payment_move.date:
                        payment_dates.append(payment_move.date)

            # Set the last payment date if any payments found
            if payment_dates:
                contract.last_payment_date = max(payment_dates)
            else:
                contract.last_payment_date = False
            print(f"[DEBUG] Last payment date for contract {contract.name}: {contract.last_payment_date}")

    # ================== changes by smit  =========================    

    def _send_sticky_notification(self, message):
        user = self.env.user
        self.env['bus.bus']._sendone(
            user.partner_id,
            'simple_notification',
            {
                'title': "Alert",
                'message': message,
                'sticky': False,
                'warning': True,
                'type': 'warning',
            }
        )

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if not record.asset_line_ids:
            record._send_sticky_notification("Warning: Please add at least one product in asset tab!")
        return record

    total_amount = fields.Float(string="Total Amount", readonly=True)

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date:
            if not self.end_date or self.end_date <= self.start_date:
                self.end_date = self.start_date + timedelta(days=364)

    @api.depends('stage_id')
    def _compute_amc_new_estimation(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'inventory_custom_tracking_installation_delivery.amc_new_estimation'
        )
        for rec in self:
            # Ensure param is 'True' and stage is 'Draft'
            if rec.stage_id == 'draft':
                rec.amc_new_estimation = param == 'True'
            else:
                rec.amc_new_estimation = False

    def _compute_visit_count(self):
        for contract in self:
            contract.visit_count = self.env['amc.contract.visit'].search_count([
                ('contract_id', '=', contract.id)
            ])

    def _compute_invoice_count(self):
        for contract in self:
            sale_orders = self.env['sale.order'].search([
                ('is_amc', '=', True),
                ('amc_contract_id', '=', contract.id)
            ])
            invoices = self.env['account.move'].search([
                ('invoice_origin', 'in', sale_orders.mapped('name')),
                ('move_type', '=', 'out_invoice')
            ])
            contract.invoice_count = len(invoices)

    def action_view_amc_invoices(self):
        self.ensure_one()
        sale_orders = self.env['sale.order'].search([
            ('is_amc', '=', True),
            ('amc_contract_id', '=', self.id)
        ])
        invoices = self.env['account.move'].search([
            ('invoice_origin', 'in', sale_orders.mapped('name')),
            ('move_type', '=', 'out_invoice')
        ])
        return {
            'name': 'AMC Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {'default_move_type': 'out_invoice', 'create': False, }
        }

    def _compute_sale_order_count(self):
        for contract in self:
            contract.sale_order_count = self.env['sale.order'].search_count([
                ('is_amc', '=', True),
                ('amc_contract_id', '=', contract.id)
            ])

    @api.onchange('sla_terms')
    def _onchange_sla_terms(self):
        if self.sla_terms:
            self.note = self.sla_terms.note
        else:
            self.note = False

    @api.depends('call_coordinator_id.phone')
    def _compute_call_coordinator_phone(self):
        """Compute the phone number based on selected Call Coordinator."""
        for task in self:
            task.call_coordinator_phone = task.call_coordinator_id.phone or False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.partner_id:
            self.call_coordinator_id = False
            self.call_coordinator_phone = False

    @api.depends('partner_id.phone')
    def _compute_partner_phone(self):
        for task in self:
            task.phone = task.partner_id.phone or False

    @api.depends('partner_id.email')
    def _compute_partner_email(self):
        for task in self:
            task.email = task.partner_id.email or False

    @api.depends('partner_id')
    def _compute_available_contacts(self):
        """
        Compute the available contacts for the selected customer.
        """
        for task in self:
            if task.partner_id:
                contacts = self.env['res.partner'].search([
                    ('parent_id', '=', task.partner_id.id),
                    ('type', 'in', ['contact', 'other'])
                ])
                for contact in contacts:
                    contact.display_name = contact.name
                task.available_contacts = contacts
            else:
                task.available_contacts = False

    @api.depends('call_coordinator_id.phone')
    def _compute_call_coordinator_phone(self):
        """Compute the phone number based on selected Call Coordinator."""
        for task in self:
            if task.call_coordinator_id.mobile:
                task.call_coordinator_phone = task.call_coordinator_id.mobile or False
            else:
                task.call_coordinator_phone = task.call_coordinator_id.phone or False

    @api.depends('partner_id')
    def _compute_service_address(self):
        for task in self:
            if task.partner_id:
                # Compute service address from main partner
                task.service_address = task.partner_id.contact_address_inline or ''

                # Find the child partner with type='invoice'
                invoice_partner = task.partner_id.child_ids.filtered(lambda p: p.type == 'invoice')
                if invoice_partner:
                    task.billing_address = invoice_partner[0].contact_address_inline or ''
                else:
                    task.billing_address = task.partner_id.contact_address_inline or ''
            else:
                task.service_address = ''
                task.billing_address = ''

    previous_contract_id = fields.Many2one(
        'amc.contract',
        string='Renewed From',
        help='Indicates this contract is a renewal of a previous contract.'
    )

    is_near_expiry = fields.Boolean(string="Is Near Expiry", compute='_compute_is_near_expiry', store=True)

    @api.depends('end_date')
    def _compute_is_near_expiry(self):
        today = fields.Date.today()
        for record in self:
            if record.end_date:
                delta = (record.end_date - today).days
                record.is_near_expiry = 0 <= delta <= 30
            else:
                record.is_near_expiry = False

    def write(self, vals):
        # Prevent date change if contract is active
        for rec in self:
            if rec.stage_id == 'active':
                if 'start_date' in vals and vals['start_date'] != rec.start_date:
                    raise ValidationError("You cannot change the Start Date when the contract is Active.")
                if 'end_date' in vals and vals['end_date'] != rec.end_date:
                    raise ValidationError("You cannot change the End Date when the contract is Active.")

        stage_id_in_vals = 'stage_id' in vals
        old_stage_map = {rec.id: rec.stage_id for rec in self}

        if stage_id_in_vals and vals.get('stage_id') == 'active':
            for rec in self:
                # Use the new start_date from vals if being updated, else the existing one
                start_date = vals.get('start_date', rec.start_date)
                if start_date and start_date > date.today():
                    raise ValidationError("You cannot activate the contract because the Start Date is in the future.")

        result = super().write(vals)

        # Stage change logic
        if stage_id_in_vals:
            for contract in self:
                old_stage = old_stage_map.get(contract.id)
                new_stage = vals['stage_id']

                # Activate: create mappings + visits
                if contract.previous_contract_id and new_stage == 'active' and old_stage != 'active':
                    contract._action_update_old_customer_mappings()
                    contract._action_create_mappings_for_new_asset_lines()
                    contract.action_generate_visits()

                elif new_stage == 'active' and old_stage != 'active':
                    contract.action_create_customer_product_mappings()
                    contract.action_generate_visits()


                elif old_stage == 'active' and new_stage in ['draft', 'cancelled']:
                    contract._action_delete_customer_product_mappings()
                    contract._action_delete_visits()

        # Sticky notification for missing asset lines
        for contract in self:
            if not contract.asset_line_ids:
                contract._send_sticky_notification("Warning: Please add at least one product in asset tab!")

        return result

    def action_replicate_renew(self):
        self.ensure_one()
        today = date.today()
        if self.end_date and self.end_date > today + timedelta(days=30):
            raise UserError("Contract is not expiring within 30 days.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Replicate & Renew',
            'res_model': 'amc.contract.renew.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
            },
        }

    def _action_update_old_customer_mappings(self):
        if not self.previous_contract_id:
            return

        old_mappings = self.env['customer.product.mapping'].search([
            ('contract_id', '=', self.previous_contract_id.id),
            ('status', '=', 'amc'),
            ('source_type', '=', 'amc'),
        ])

        for mapping in old_mappings:
            # Try to find a matching asset line in the new contract
            matching_asset_lines = self.asset_line_ids.filtered(lambda line:
                                                                line.product_id == mapping.product_id and
                                                                set(line.serial_number_ids.ids) == set(
                                                                    mapping.serial_number_ids.ids) and
                                                                line.visit == mapping.visit
                                                                )

            if not matching_asset_lines:
                continue

            # Merge case (multiple lines matching one mapping)
            combined_user_ids = matching_asset_lines.mapped('user_ids')
            all_new_user_ids = set(user.id for user in combined_user_ids if user)
            total_quantity = sum(matching_asset_lines.mapped('quantity'))

            # Only update user_ids if they differ
            existing_user_ids = set(mapping.user_ids.ids)
            if all_new_user_ids != existing_user_ids:
                mapping.write({
                    'contract_id': self.id,
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'user_ids': [(6, 0, list(all_new_user_ids))],
                    'quantity': total_quantity,
                })
            else:
                # Only update contract/dates if user_ids are same
                mapping.write({
                    'contract_id': self.id,
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                })

    def _action_create_mappings_for_new_asset_lines(self):
        if not self.previous_contract_id:
            return

        old_assets = []
        for line in self.previous_contract_id.asset_line_ids:
            old_assets.append({
                'product_id': line.product_id.id,
                'serial_ids': set(line.serial_number_ids.ids),
                'visit': line.visit,
            })
        # Prepare merged products (no serial number case)
        merged_products = {}
        for asset in self.asset_line_ids:
            is_existing = any(
                asset.product_id.id == old['product_id'] and
                set(asset.serial_number_ids.ids) == old['serial_ids'] and
                asset.visit == old['visit']
                for old in old_assets
            )
            if is_existing:
                continue  # Skip already handled asset line

            product_id = asset.product_id.id
            user_ids = asset.user_ids.ids if asset.user_ids else []

            if not asset.serial_number_ids:
                merge_key = (product_id, asset.visit)

                if merge_key not in merged_products:
                    merged_products[merge_key] = {
                        'product': asset.product_id,
                        'visit': asset.visit,
                        'total_quantity': 0.0,
                        'user_ids': set(),
                    }
                merged_products[merge_key]['total_quantity'] += asset.quantity or 0.0
                merged_products[merge_key]['user_ids'].update(user_ids)
            else:
                # Create individual mapping for assets with serial numbers
                self.env['customer.product.mapping'].create({
                    'customer_id': self.partner_id.id,
                    'product_id': product_id,
                    'status': 'amc',
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'source_type': 'amc',
                    'serial_number_ids': asset.serial_number_ids.id,
                    'contract_id': self.id,
                    'product_category': asset.product_id.categ_id.id,
                    'unique_number': self.env['ir.sequence'].next_by_code('customer.product.mapping'),
                    'quantity': asset.quantity or 0.0,
                    'user_ids': [(6, 0, user_ids)] if user_ids else False,
                    'contract_type': self.contract_type.id,
                    'visit': asset.visit,
                })

        # Create merged customer mappings for non-serial products
        for (product_id, visit), merged_data in merged_products.items():
            self.env['customer.product.mapping'].create({
                'customer_id': self.partner_id.id,
                'product_id': product_id,
                'status': 'amc',
                'start_date': self.start_date,
                'end_date': self.end_date,
                'source_type': 'amc',
                'contract_id': self.id,
                'product_category': merged_data['product'].categ_id.id,
                'unique_number': self.env['ir.sequence'].next_by_code('customer.product.mapping'),
                'quantity': merged_data['total_quantity'],
                'user_ids': [(6, 0, list(merged_data['user_ids']))] if merged_data['user_ids'] else False,
                'contract_type': self.contract_type.id,
                'visit': visit,
            })

    def action_create_customer_product_mappings(self):
        for contract in self:
            # Validations
            if contract.stage_id != 'active':
                raise UserError("Product mapping can only be created if the contract is in 'Active' stage.")
            if not contract.partner_id:
                raise UserError("Customer is required to create product mappings.")
            if not contract.asset_line_ids:
                raise UserError("No asset lines found to create product mappings.")

            self.env['customer.product.mapping'].search([
                ('contract_id', '=', contract.id),
                ('status', '=', 'amc'),
                ('source_type', '=', 'amc'),
            ]).unlink()

            # Group (product_id, visit) for non-serial products
            merged_products = {}

            for asset in contract.asset_line_ids:
                if not asset.product_id:
                    raise UserError("Product is missing on asset line.")

                product_id = asset.product_id.id
                user_ids = asset.user_ids.ids if hasattr(asset, 'user_ids') else []

                if not asset.serial_number_ids:
                    # Group by (product_id, visit)
                    merge_key = (product_id, asset.visit)

                    if merge_key not in merged_products:
                        merged_products[merge_key] = {
                            'product': asset.product_id,
                            'visit': asset.visit,
                            'total_quantity': 0.0,
                            'user_ids': set(),
                        }

                    merged_products[merge_key]['total_quantity'] += asset.quantity or 0.0
                    merged_products[merge_key]['user_ids'].update(user_ids)

                else:
                    # Create individual mapping for assets with serial numbers
                    self.env['customer.product.mapping'].create({
                        'customer_id': contract.partner_id.id,
                        'product_id': product_id,
                        'status': 'amc',
                        'start_date': contract.start_date or fields.Date.today(),
                        'end_date': contract.end_date or (fields.Date.today() + timedelta(days=365)),
                        'source_type': 'amc',
                        'serial_number_ids': asset.serial_number_ids.id,  # no 's' at end
                        'contract_id': contract.id,
                        'product_category': asset.product_id.categ_id.id,
                        'unique_number': self.env['ir.sequence'].next_by_code('customer.product.mapping'),
                        'quantity': asset.quantity or 0.0,
                        'user_ids': [(6, 0, user_ids)],
                        'contract_type': contract.contract_type.id,
                        'visit': asset.visit,
                    })

            # Create merged customer mappings for non-serial products
            for (product_id, visit), merged_data in merged_products.items():
                self.env['customer.product.mapping'].create({
                    'customer_id': contract.partner_id.id,
                    'product_id': product_id,
                    'status': 'amc',
                    'start_date': contract.start_date or fields.Date.today(),
                    'end_date': contract.end_date or (fields.Date.today() + timedelta(days=365)),
                    'source_type': 'amc',
                    'serial_number_ids': asset.serial_number_ids.id,  # no 's' at end
                    'contract_id': contract.id,
                    'product_category': merged_data['product'].categ_id.id,
                    'unique_number': self.env['ir.sequence'].next_by_code('customer.product.mapping'),
                    'quantity': merged_data['total_quantity'],
                    'user_ids': [(6, 0, list(merged_data['user_ids']))],
                    'contract_type': contract.contract_type.id,
                    'visit': visit,
                })

    def _action_delete_customer_product_mappings(self):
        for contract in self:
            self.env['customer.product.mapping'].search([
                ('contract_id', '=', contract.id),
                ('status', '=', 'amc'),
                ('source_type', '=', 'amc'),
            ]).unlink()

    def action_open_sale_order(self):
        self.ensure_one()

        if not self.asset_line_ids:
            raise UserError("No asset lines found to create order lines.")

        order_lines = []
        for asset in self.asset_line_ids:
            if not asset.product_id:
                raise UserError("Product is missing in one of the asset lines.")
            order_lines.append((0, 0, {
                'product_id': asset.product_id.id,
                'product_uom_qty': asset.quantity or 1.0,
                'price_unit': asset.cost or asset.product_id.lst_price,
            }))

        return {
            'name': 'Create Sales Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_origin': self.name,
                'default_is_amc': True,
                'default_amc_contract_id': self.id,
                'default_order_line': order_lines,
                'default_note': self.note or '',
                'default_unit_status': 'amc',
            }
        }

    def action_view_amc_sale_orders(self):
        self.ensure_one()
        return {
            'name': 'AMC Sale Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('is_amc', '=', True), ('amc_contract_id', '=', self.id)],
            'context': {'default_amc_contract_id': self.id, 'create': False}
        }

    def action_generate_visits(self):
        for contract in self:
            if not contract.start_date or not contract.end_date:
                raise UserError("Start Date and End Date must be set.")

            # Clear previous visits
            contract.visit_ids.unlink()

            start_date = contract.start_date
            end_date = contract.end_date
            total_days = (end_date - start_date).days
            if total_days <= 0:
                raise UserError("End Date must be after Start Date.")

            grouped_assets = {}  # Key: (product_id, visit_interval)
            individual_assets = []  # For serial-number-based assets

            # Step 1: Group non-serial-number assets by (product, visit)
            for line in contract.asset_line_ids:
                if not line.product_id:
                    continue

                # Handle serial-number-based assets separately
                if line.serial_number_ids:
                    individual_assets.append(line)
                    continue

                # Skip assets with no visit
                if not line.visit or line.visit <= 0:
                    continue

                key = (line.product_id.id, line.visit)
                if key not in grouped_assets:
                    grouped_assets[key] = {
                        'lines': [],
                        'user_ids': set(),
                        'visit': line.visit,
                    }

                grouped_assets[key]['lines'].append(line)
                if line.user_ids:
                    grouped_assets[key]['user_ids'].add(line.user_ids.id)

            # Step 2: Create visits for grouped assets
            for group in grouped_assets.values():
                visit_interval = group['visit']
                delta_days = visit_interval * 30
                visit_date = start_date + timedelta(days=delta_days)

                while visit_date <= end_date:
                    self.env['amc.contract.visit'].create({
                        'contract_id': contract.id,
                        'visit_date': visit_date,
                        'technician_ids': [(6, 0, list(group['user_ids']))],
                    })
                    visit_date += timedelta(days=delta_days)

            # Step 3: Handle individual serial-number-based assets
            for asset in individual_assets:
                visit_interval = asset.visit
                if not visit_interval or visit_interval <= 0:
                    continue

                delta_days = visit_interval * 30
                visit_date = start_date + timedelta(days=delta_days)
                tech_id = asset.user_ids.id if asset.user_ids else False

                while visit_date <= end_date:
                    self.env['amc.contract.visit'].create({
                        'contract_id': contract.id,
                        'visit_date': visit_date,
                        'technician_ids': [(6, 0, [tech_id])] if tech_id else False,
                    })
                    visit_date += timedelta(days=delta_days)

    def _action_delete_visits(self):
        for contract in self:
            contract.visit_ids.unlink()

    def action_view_amc_visits(self):
        self.ensure_one()
        return {
            'name': 'Scheduled Visits',
            'type': 'ir.actions.act_window',
            'res_model': 'amc.contract.visit',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'create': False, 'search_default_upcoming_visits': 1},
        }

    def download_customer_pdf(self):
        self.ensure_one()
        # return self.env.ref('inventory_custom_tracking_installation_delivery.report_amc_customer_pdf').report_action(self)

        try:
            if self.contract_type and self.contract_type.name == 'AMC':
                customizer = self.env['xml.upload'].search([
                    ('model_id.model', '=', 'amc.contract'),
                    ('report_action', '=', 'action_xml_upload_custom_report_format_for_all_amc_contract'),
                    ('xml_file', '!=', False),
                ], limit=1)

                if customizer and customizer.xml_file:
                    return self.env.ref(
                        'data_recycle.action_xml_upload_custom_report_format_for_all_amc_contract'
                    ).report_action(self)
                else:
                    return self.env.ref(
                        'inventory_custom_tracking_installation_delivery.report_amc_customer_pdf'
                    ).report_action(self)

            elif self.contract_type and self.contract_type.name == 'CMC':
                print("1")
                customizer = self.env['xml.upload'].search([
                    ('model_id.model', '=', 'amc.contract'),
                    ('report_action', '=', 'action_xml_upload_custom_report_format_for_all_cmc_contract'),
                    ('xml_file', '!=', False),
                ], limit=1)

                if customizer and customizer.xml_file:
                    return self.env.ref(
                        'data_recycle.action_xml_upload_custom_report_format_for_all_cmc_contract'
                    ).report_action(self)
                else:
                    return self.env.ref(
                        'inventory_custom_tracking_installation_delivery.report_cmc_customer_pdf'
                    ).report_action(self)

            else:
                raise UserError("Unknown contract type. Cannot generate report.")

        except ValueError:
            if self.contract_type and self.contract_type.name == 'AMC':
                return self.env.ref(
                    'inventory_custom_tracking_installation_delivery.report_amc_customer_pdf'
                ).report_action(self)
            elif self.contract_type and self.contract_type.name == 'CMC':
                return self.env.ref(
                    'inventory_custom_tracking_installation_delivery.report_cmc_customer_pdf'
                ).report_action(self)
            else:
                raise UserError("Unknown contract type during fallback.")
        except Exception as e:
            raise UserError(f"Failed to generate customer report: {str(e)}")


class ProductMapping(models.Model):
    _inherit = 'customer.product.mapping'

    contract_id = fields.Many2one(
        'amc.contract',
        string='AMC Contract',
        tracking=True,
        ondelete='set null'
    )
    quantity = fields.Float(string="Quantity")
    user_ids = fields.Many2many(comodel_name='res.users', string="Assignee")
    contract_type = fields.Many2one(comodel_name='contract.type', string="Contract Type", tracking=True)
    visit = fields.Integer(string="Visit")

    @api.onchange('customer_id')
    def _onchange_customer_id_contract(self):
        if not self.customer_id:
            self.contract_id = False
        else:
            # Filter contract based on customer_id
            contracts = self.env['amc.contract'].search([('partner_id', '=', self.customer_id.id)])
            # If current contract does not belong to customer, reset it
            if self.contract_id and self.contract_id.partner_id != self.customer_id:
                self.contract_id = False
            # Optional: if no contract selected but customer has contracts, you can preselect one here
            # self.contract_id = contracts and contracts[0] or False

    @api.onchange('contract_id')
    def _onchange_contract_id_customer(self):
        if self.contract_id:
            self.customer_id = self.contract_id.partner_id
            self.contract_type = self.contract_id.contract_type
        else:
            if not self.env.context.get('default_customer_id'):
                self.customer_id = False
            self.contract_type = False


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_amc = fields.Boolean(string="Is AMC Order", default=False)
    amc_contract_id = fields.Many2one('amc.contract', string="AMC Contract")

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            contract = order.amc_contract_id
            if contract:
                # 1. Update total with this order's value
                contract.total_amount = order.amount_total

                # 2. Set contract stage to active if not already
                if contract.start_date == date.today() and contract.stage_id != 'active':
                    contract.stage_id = 'active'
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for order in self:
            contract = order.amc_contract_id
            if contract:
                # Find latest confirmed sale order for this contract
                latest_confirmed = self.env['sale.order'].search([
                    ('amc_contract_id', '=', contract.id),
                    ('state', 'in', ['sale', 'done'])
                ], order="id desc", limit=1)

                # Update total and (optional) stage
                contract.total_amount = latest_confirmed.amount_total if latest_confirmed else 0.0

                # Optional: revert stage to 'draft' if no active sale orders
                if not latest_confirmed:
                    contract.stage_id = 'draft'
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_amc = fields.Boolean(string="Is AMC", copy=False, tracking=True)
    amc_contract_id = fields.Many2one('amc.contract', string="AMC Contract")

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            # Try to find sale order from origin
            if move.move_type == 'out_invoice' and move.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', move.invoice_origin)], limit=1)
                if sale_order:
                    move.is_amc = sale_order.is_amc
                    move.amc_contract_id = sale_order.amc_contract_id
        return moves


class AmcContractVisit(models.Model):
    _name = 'amc.contract.visit'
    _description = 'AMC Contract Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date asc'

    contract_id = fields.Many2one('amc.contract', string="AMC Contract", required=True, ondelete='cascade')
    visit_date = fields.Date(string="Scheduled Visit Date", required=True)
    technician_ids = fields.Many2many('res.users', string="Assigned Technicians")
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], default='pending', string="Status", tracking=True)
    note = fields.Text(string="Visit Note")
    task_ids = fields.One2many('project.task', 'amc_visit_id', string="Service Call Tasks")

    def create_service_call(self):
        """Create a service call (project.task) for this visit"""
        self.ensure_one()

        if not self.contract_id or not self.contract_id.partner_id:
            return False

        # Get the FSM project
        fsm_project = self.env['project.project'].search([('is_fsm', '=', True)], limit=1)
        if not fsm_project:
            raise UserError("No FSM project found. Please create one first.")

        # Get the 'New' stage
        new_stage = self.env['project.task.type'].search([
            ('name', '=', 'Assigned'),
            ('project_ids.is_fsm', '=', True)
        ], limit=1)

        # Find matching customer product mapping
        # We will check all mappings for this contract and customer, and filter by exact technician match
        matching_mapping = False
        for mapping in self.env['customer.product.mapping'].search([
            ('contract_id', '=', self.contract_id.id),
            ('customer_id', '=', self.contract_id.partner_id.id),
        ]):
            mapping_user_ids = set(mapping.user_ids.ids)
            visit_user_ids = set(self.technician_ids.ids)

            if mapping_user_ids == visit_user_ids:
                matching_mapping = mapping
                break  # First exact match found

        # Create the task
        task_vals = {
            'name': f"{self.contract_id.contract_type.name} Visit - {self.contract_id.name}",
            'partner_id': self.contract_id.partner_id.id,
            'call_type': self.env.ref('industry_fsm.call_type_amc', raise_if_not_found=False).id,
            'call_sub_types': 'normal_call',
            'is_fsm': True,
            'planned_date_begin': datetime.combine(self.visit_date, time(3, 30)),
            'date_deadline': datetime.combine(self.visit_date, time(5, 30)),
            'department_id': self.env['hr.department'].search([('name', '=', 'Service Division')], limit=1).id,
            'user_ids': [(6, 0, self.technician_ids[:1].ids)],
            'project_id': fsm_project.id,
            'stage_id': new_stage.id if new_stage else False,
            'call_coordinator_id': self.contract_id.call_coordinator_id.id,
            'customer_product_id': matching_mapping.id if matching_mapping else False,
            # 'serial_number': [(6, 0, matching_mapping.serial_number_ids.ids)] if matching_mapping else False,
            'serial_number': matching_mapping.serial_number_ids.id if matching_mapping and matching_mapping.serial_number_ids else False,

        }

        task = self.env['project.task'].create(task_vals)

        # Link the visit to the task
        task.amc_visit_id = self.id

        return task


class AmcVisitScheduler(models.Model):
    _name = 'amc.visit.scheduler'
    _description = 'AMC Visit Scheduler'

    @api.model
    def create_service_calls_for_today(self):
        """Create service calls for visits X days in future, based on system config"""
        today = fields.Date.today()

        # Get number of days in advance from settings
        days_before = int(self.env['ir.config_parameter'].sudo().get_param(
            'inventory_custom_tracking_installation_delivery.days_before_schedule_visit', default=0))

        target_visit_date = today + timedelta(days=days_before)

        # Find all visits scheduled on that future date that are still pending
        visits = self.env['amc.contract.visit'].search([
            ('visit_date', '=', target_visit_date),
            # ('state', '=', 'pending'),
        ])

        for visit in visits:
            try:
                visit.create_service_call()
            except Exception as e:
                _logger.error(f"Failed to create service call for visit {visit.id}: {str(e)}")


class ProjectTask(models.Model):
    _inherit = 'project.task'

    amc_visit_id = fields.Many2one(
        'amc.contract.visit',
        string="AMC Visit",
        ondelete='set null'
    )
