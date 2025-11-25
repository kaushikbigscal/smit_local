from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)
import base64
import binascii



class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_distributor = fields.Boolean(string="Is Distributor")

    enable_distributor = fields.Boolean(
        string='Enable Distributor',
        compute='_compute_enable_distributor',
        store=False
    )

    @api.depends_context('uid')  # recompute per user session if needed
    def _compute_enable_distributor(self):
        enable = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
        for rec in self:
            rec.enable_distributor = bool(enable and enable not in ['False', '0'])

    @api.onchange('partner_id', 'sale_id')
    def _onchange_partner_sale(self):
        for picking in self:
            if (picking.sale_id and
                    picking.sale_id.sale_order_type == 'primary_orders' and
                    picking.partner_id and
                    picking.partner_id.company_type == 'distribution'):

                warehouse_loc = picking.partner_id.warehouse_id.lot_stock_id
                if warehouse_loc:
                    picking.location_dest_id = warehouse_loc.id


    @api.model
    def _action_done(self):
        CustomerAsset = self.env['customer.product.mapping']
        DistributorAsset = self.env['distributor.asset']

        enable_distributor = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
        if not enable_distributor:
            return super()._action_done()

        for picking in self:
            sale_order = picking.sale_id
            if not sale_order:
                continue

            # Distributor Assets - ONLY for primary orders
            if sale_order.sale_order_type == 'primary_orders' and sale_order.distributor_id:
                distributor_id = sale_order.distributor_id.id
                for move in picking.move_ids_without_package:
                    product_tmpl_id = move.product_id.product_tmpl_id.id

                    if move.product_id.tracking != 'none':
                        lot_ids = move.move_line_ids.lot_id.ids
                        if lot_ids:
                            existing_assets = DistributorAsset.search([
                                ('lot_id', 'in', lot_ids),
                                ('product_id', '=', product_tmpl_id)
                            ])
                            existing_lot_ids = set(existing_assets.mapped('lot_id').ids)

                            for ml in move.move_line_ids:
                                lot_id = ml.lot_id.id
                                if not lot_id or lot_id in existing_lot_ids:
                                    continue
                                DistributorAsset.create({
                                    'distributor_id': distributor_id,
                                    'product_id': product_tmpl_id,
                                    'status': 'unallocated',
                                    'lot_id': lot_id,
                                })
                    else:
                        qty = int(move.product_uom_qty)
                        DistributorAsset.create([{
                            'distributor_id': distributor_id,
                            'product_id': product_tmpl_id,
                            'status': 'unallocated',
                            'lot_id': False,
                        } for _ in range(qty)])

            # Customer Assets - secondary or direct orders
            if sale_order.sale_order_type in ['secondary_orders', 'direct_orders']:
                distributor_id = sale_order.distributor_id.id if sale_order.sale_order_type == 'secondary_orders' else False

                # --- For secondary orders mark distributor assets allocated ---
                if sale_order.sale_order_type == 'secondary_orders':
                    for move in picking.move_ids_without_package:
                        product_tmpl_id = move.product_id.product_tmpl_id.id
                        serials = move.move_line_ids.lot_id.ids
                        if not sale_order.exists():
                            continue

                        if serials:
                            unallocated_assets = DistributorAsset.search([
                                ('lot_id', 'in', serials),
                                ('product_id', '=', product_tmpl_id),
                                ('distributor_id', '=', distributor_id),
                                ('status', '=', 'unallocated'),
                            ])
                            lot2asset = {a.lot_id.id: a for a in unallocated_assets}

                            for lot_id in serials:
                                asset = lot2asset.get(lot_id)
                                if asset:
                                    asset.status = 'allocated'
                                else:
                                    lot_name = self.env['stock.lot'].browse(lot_id).name
                                    _logger.info(f"No unallocated asset found for Lot {lot_name}")
                        else:
                            qty = int(move.product_uom_qty)
                            unallocated_assets = DistributorAsset.search([
                                ('product_id', '=', product_tmpl_id),
                                ('distributor_id', '=', distributor_id),
                                ('status', '=', 'unallocated')
                            ], limit=qty)
                            unallocated_assets.write({'status': 'allocated'})

                # --- Skip excluded moves ---
                excluded_move_ids = set(picking.picking_parts_ids.mapped("move_id").ids)

                Project = self.env['project.project'].sudo()
                project = Project.search([('name', '=', 'Service Call')], limit=1)
                if not project:
                    project = Project.create({'name': 'Service Call', 'is_fsm': True})

                now = fields.Datetime.now()

                for move in picking.move_ids:
                    if move.id in excluded_move_ids:
                        continue

                    product = move.product_id
                    product_tmpl = product.product_tmpl_id
                    serials = move.move_line_ids.lot_id

                    if serials:
                        serial_list = serials
                        qty_list = [1] * len(serials)
                    else:
                        qty = int(move.product_uom_qty)
                        serial_list = [None] * qty
                        qty_list = [1] * qty

                    installation_attachments = self.env['installation.attachment.line']
                    if product_tmpl:
                        installation_attachments |= product_tmpl.installation_attachment_line_ids.filtered(
                            'upload_file')
                    if product.categ_id:
                        installation_attachments |= product.categ_id.installation_attachment_line_ids.filtered(
                            'upload_file')

                    for idx, (lot, qty) in enumerate(zip(serial_list, qty_list), start=1):
                        order_line = move.sale_line_id or self.env['sale.order.line'].search([
                            ('order_id', '=', sale_order.id),
                            ('product_id', '=', product.id)
                        ], limit=1)

                        unit_status = (order_line.unit_status if order_line else None) or 'chargeable'

                        # Normal warranty
                        if unit_status == 'warranty' and order_line:
                            start_date = sale_order.warranty_start_date or fields.Date.today()
                            end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
                        else:
                            start_date = fields.Date.today()
                            end_date = fields.Date.today() + timedelta(days=1)

                        extended_start = False
                        extended_end = False

                        # if sale_order:
                        #     extended_line = sale_order.order_line.filtered(
                        #         lambda l: l.is_extended_warranty and product.display_name in (l.name or "")
                        #     )
                        #     if extended_line:
                        #         desc = extended_line[0].name or ""
                        #         _logger.info(f"🔍 Extracting warranty dates from description: {desc}")
                        #
                        #         import re
                        #         from datetime import datetime as dt
                        #         match = re.search(
                        #             r'from\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                        #             desc, re.IGNORECASE
                        #         )
                        #         if match:
                        #             try:
                        #                 start_str, end_str = match.groups()
                        #                 start_str = start_str.replace('/', '-')
                        #                 end_str = end_str.replace('/', '-')
                        #                 extended_start = dt.strptime(start_str, "%d-%m-%Y").date()
                        #                 extended_end = dt.strptime(end_str, "%d-%m-%Y").date()
                        #                 _logger.info(
                        #                     f"Extracted Extended Dates → Start: {extended_start}, End: {extended_end}")
                        #             except Exception as e:
                        #                 _logger.warning(f"Date parse failed for extended warranty: {e}")
                        #         else:
                        #             _logger.debug(f"No date pattern found in: {desc}")

                        # Call type
                        call_type_value = False
                        if unit_status:
                            call_type_rec = self.env['call.type'].sudo().search(
                                [('name', 'ilike', unit_status.strip())], limit=1)
                            if call_type_rec:
                                call_type_value = call_type_rec.id

                        if picking.partner_id:
                            existing_asset = CustomerAsset.search([
                                ('customer_id', '=', picking.partner_id.id),
                                ('product_id', '=', product.id),
                                ('serial_number_ids', '=', lot.id if lot else False),
                                ('order_id', '=', order_line.id if order_line else False)
                            ], limit=1)

                            if existing_asset:
                                vals_to_update = {}
                                if not existing_asset.distributor_id and distributor_id:
                                    vals_to_update['distributor_id'] = distributor_id
                                if not existing_asset.asset_status:
                                    vals_to_update['asset_status'] = 'allocated'

                                vals_to_update.update({
                                    'start_date': start_date,
                                    'end_date': end_date,
                                    # 'extended_start_date': extended_start,
                                    # 'extended_end_date': extended_end,
                                    'status': unit_status,
                                })

                                existing_asset.write(vals_to_update)
                                customer_asset = existing_asset
                            else:
                                customer_asset = CustomerAsset.create({
                                    'customer_id': picking.partner_id.id,
                                    'product_id': product.id,
                                    'serial_number_ids': lot.id if lot else False,
                                    'order_id': order_line.id if order_line else False,
                                    'source_type': 'sale_order' if sale_order.sale_order_type in ['secondary_orders',
                                                                                                  'direct_orders'] else 'direct_product',
                                    'start_date': start_date,
                                    'end_date': end_date,
                                    # 'extended_start_date': extended_start,
                                    # 'extended_end_date': extended_end,
                                    'asset_status': 'allocated',
                                    'status': unit_status,
                                    'product_category': product.categ_id.id or False,
                                    'distributor_id': distributor_id,
                                })

                        # Installation call creation
                        if product_tmpl.installed_ok:
                            installation_html = self._get_html_for_product(order_line, product) if order_line else ''
                            desc_html = f"<p>Installation call for product {product.name} (Serial: {lot.name if lot else 'No Serial'})</p>"
                            if installation_html:
                                desc_html += installation_html

                            # --------------------------------------------
                            # ⚙️ Auto Fetch Department & assignee Logic
                            # --------------------------------------------
                            department_id = False
                            assigned_users = []
                            dept_service = False

                            # No technicians assigned -> find department by partner city
                            partner = picking.partner_id
                            partner_city = partner.city_id.name if hasattr(partner,
                                                                           'city_id') and partner.city_id else partner.city
                            partner_state = partner.state_id.name if partner.state_id else False

                            if partner_city:
                                dept_service = self.env['department.service'].sudo().search([
                                    ('city_id.name', 'ilike', partner_city)
                                ], limit=1)

                            else:
                                # No city_id → match by state
                                if partner_state:
                                    dept_service = self.env['department.service'].sudo().search([
                                        ('state_id.name', 'ilike', partner_state)
                                    ], limit=1)

                            if dept_service and dept_service.department_id:
                                department_id = dept_service.department_id.id

                                # Find users in that department
                                department_users = self.env['res.users'].sudo().search([
                                    ('employee_ids.department_id', '=', department_id)
                                ])

                                assigned_user = None

                                # Try FSM Supervisors first (not Managers)
                                supervisors = department_users.filtered(
                                    lambda u: u.has_group('industry_fsm.group_fsm_supervisor')
                                              and not u.has_group('industry_fsm.group_fsm_manager')
                                )

                                if supervisors:
                                    assigned_user = supervisors[0]
                                else:
                                    # Fallback: FSM Manager in that department
                                    managers = department_users.filtered(
                                        lambda u: u.has_group('industry_fsm.group_fsm_manager')
                                    )
                                    if managers:
                                        assigned_user = managers[0]

                                if assigned_user:
                                    assigned_users = [assigned_user.id] or []

                            task_vals = {
                                'name': f"Installation Call - {product.name}",
                                'project_id': project.id,
                                'is_fsm': True,
                                'partner_id': picking.partner_id.id,
                                'customer_product_id': customer_asset.id,
                                'department_id': department_id,
                                'user_ids': [(6, 0, assigned_users)],
                                'serial_number': customer_asset.serial_number_ids.id or False,
                                'installation_table_html': desc_html,
                                'call_type': call_type_value,
                            }
                            task = self.env['project.task'].sudo().create(task_vals)

                            for attach in installation_attachments:
                                try:
                                    file_data = base64.b64decode(attach.upload_file, validate=True)
                                except (binascii.Error, ValueError):
                                    _logger.warning(f"Invalid file in installation attachment {attach.name}, skipped.")
                                    continue
                                filename = attach.upload_file_filename or attach.name or "attachment.dat"
                                task.message_post(
                                    body=f"Installation Checklist: {attach.name}",
                                    attachments=[(filename, file_data)],
                                    message_type='comment',
                                    subtype_xmlid='mail.mt_comment'
                                )

        return super()._action_done()
 
        
        


    def _get_html_for_product(self, order_line, product):
        """Return installation HTML table for a product:
           - show attachments once
           - show dynamic fields per order line separately
        """
        InstallationLine = self.env['sale.order.installation.line']

        # All lines for this product in the order
        all_lines = InstallationLine.search([
            ('order_id', '=', order_line.order_id.id),
            ('product_id', '=', product.product_tmpl_id.id)
        ])

        if not all_lines:
            return ""

        html = ""

        # --- Attachments (shared across product) ---
        attachment_lines = all_lines.filtered(lambda l: l.file)
        if attachment_lines:
            html += """
            <h4>Attachments</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Attachment Name</th>
                        <th style="padding:6px; text-align:left;">File</th>
                    </tr>
                </thead>
                <tbody>
            """
            for line in attachment_lines:
                file_link = f'/web/content/{line._name}/{line.id}/file/{line.file_name}?download=true'
                file_link_html = f'<a href="{file_link}">{line.file_name or "Download"}</a>'
                html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600;">{line.attachment_name}</td>
                        <td style="padding:6px;">{file_link_html}</td>
                    </tr>
                """
            html += "</tbody></table>"

        # --- Dynamic Fields (per order line) ---
        # take only lines of this order_line
        dynamic_lines = all_lines.filtered(
            lambda l: not l.file and l.sale_line_id.id == order_line.id
        )
        if dynamic_lines:
            html += """
            <h4>Custom Fields</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Field</th>
                        <th style="padding:6px; text-align:left;">Value</th>
                    </tr>
                </thead>
                <tbody>
            """
            for line in dynamic_lines:
                html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600;">{line.attachment_name}</td>
                        <td style="padding:6px;">{line.product_display_name or ''}</td>
                    </tr>
                """
            html += "</tbody></table>"

        # Save to order for later display if you want
        order_line.order_id.installation_table_html = html

        return html

