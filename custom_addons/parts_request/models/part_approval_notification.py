from odoo import models, fields, api,_
from odoo.exceptions import UserError, AccessError


class PartApprovalNotification(models.Model):
    _name = 'part.approval.notification'
    _description = 'Part Approval Notification'
    _rec_name = 'task_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    task_id = fields.Many2one('project.task', string='Call Name', readonly=True)
    # product_tmpl_id = fields.Many2one('product.template', string='Product')
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    part_id = fields.Many2one('project.task.part', string='Part', readonly=True)
    user_ids = fields.Many2many('res.users',string="Assignee",readonly=True)
    part_name = fields.Char(string='Part Name', readonly=True)  # human-readable part name
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor', readonly=True)
    message = fields.Text(string='Notification Message')
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    coverage = fields.Selection([
        ('foc', 'FOC'),
        ('chargeable', 'Chargeable')
    ], string='Coverage', readonly=True)
    sequence_fsm = fields.Char(
        string='Ticket Number',
        related='task_id.sequence_fsm',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('waiting_warehouse_manager', 'Waiting Warehouse Manager'),
        ('shipment', 'Shipment'),
        ('pick_up', 'Pick up'),
        ('received', 'Received'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    show_pick_up_button = fields.Boolean(
        string="Show Pick Up Button",
        compute="_compute_show_pick_up_button"
    )

    @api.depends('status', 'company_id.enable_direct_pickup')
    def _compute_show_pick_up_button(self):
        for rec in self:
            company_flag = rec.company_id.enable_direct_pickup
            rec.show_pick_up_button = company_flag and rec.status == 'shipment'

    enable_warehouse = fields.Selection(
        [('external_warehouse', 'External Warehouse'),
         ('internal_warehouse', 'Internal Warehouse')],
        related='company_id.enable_warehouse',
        store=False,
    )
    show_stock_button = fields.Boolean(
        string="Show Stock Button",
        compute="_compute_show_stock_button"
    )

    @api.depends('company_id.enable_warehouse')
    def _compute_show_stock_button(self):
        for rec in self:
            rec.show_stock_button = rec.company_id.enable_warehouse == 'internal_warehouse'


    def action_approve(self):
        print("action_approve called")
        for rec in self:

            if rec.company_id.enable_warehouse != 'internal_warehouse':
                print("\n\n--- Skipping Warehouse logic: Company set to External Warehouse ---\n\n")
                continue

            print(f"Approving notification id={rec.id}, part_name={rec.part_name}")
            rec.status = 'approved'

            # Update the related part's stage to 'approved'
            if rec.part_id:
                rec.part_id.status = 'approved'

            task = rec.task_id if hasattr(rec, 'task_id') else rec

            supervisor = task.department_id.manager_id if task.department_id else False
            current_user = self.env.user

            # Access control: Only Supervisor can approve
            if not supervisor or not supervisor.user_id:
                raise AccessError(_("No supervisor is assigned to this task, approval cannot proceed."))

            if current_user.id != supervisor.user_id.id:
                raise AccessError(
                    _("You are not allowed to approve this request. Only the Supervisor (%s) can approve this part request.")
                    % supervisor.name)

            part_name = rec.part_id.product_id.display_name or rec.part_id.display_name or rec.part_name or _("Unnamed Part")
            print("part name:", part_name)

            # Send notification to Task Assignee
            if task.user_ids:
                for user in task.user_ids:
                    partner = user.partner_id
                    print("partner name:",partner)
                    if not partner:
                        print("No Partner Linked for user:", user.name)
                        continue

                    print("Sending notification to Task Assignee:", user.name, "| Partner ID:", partner.id)

                    task.message_notify(
                        body= _(
                                "Supervisor %s has approved your request for the part %s."
                            ) % (self.env.user.name, part_name),
                        subject=f"Assignee Notification - {task.name}",
                        record_name=rec.display_name,
                        partner_ids=[partner.id],
                        subtype_xmlid='mail.mt_comment',
                    )

                    print("Notification sent to Task Assignee:", user.name)

    def action_reject(self):
        print("action_reject called")
        for rec in self:

            if rec.company_id.enable_warehouse != 'internal_warehouse':
                print("\n\n--- Skipping Warehouse logic: Company set to External Warehouse ---\n\n")
                continue

            print(f"Rejecting notification id={rec.id}, part_name={rec.part_name}")
            rec.status = 'rejected'

            # Update the related part's stage to 'rejected'
            if rec.part_id:
                rec.part_id.status = 'rejected'

            task = rec.task_id if hasattr(rec, 'task_id') else rec

            supervisor = task.department_id.manager_id if task.department_id else False
            current_user = self.env.user

            # Access control: Only Supervisor can approve
            if not supervisor or not supervisor.user_id:
                raise AccessError(_("No supervisor is assigned to this task, approval cannot proceed."))

            if current_user.id != supervisor.user_id.id:
                raise AccessError(
                    _("You are not allowed to Reject this request. Only the Supervisor (%s) can reject this part request.")
                    % supervisor.name)

            part_name = rec.part_id.product_id.display_name or rec.part_id.display_name or rec.part_name or _("Unnamed Part")
            print("part name:", part_name)

            # Send notification to Task Assignee
            if task.user_ids:
                for user in task.user_ids:
                    partner = user.partner_id
                    print("partner name:",partner)
                    if not partner:
                        print("No Partner Linked for user:", user.name)
                        continue

                    print("Sending notification to Task Assignee:", user.name, "| Partner ID:", partner.id)

                    task.message_notify(
                        body= _(
                                "Supervisor %s has reject your request for the part %s."
                            ) % (self.env.user.name, part_name),
                        subject=f"Assignee Notification - {task.name}",
                        record_name=rec.display_name,
                        partner_ids=[partner.id],
                        subtype_xmlid='mail.mt_comment',
                    )

                    print("Notification sent to Task Assignee:", user.name)

    def action_request_warehouse_manager(self):
        for rec in self:
            if rec.company_id.enable_warehouse != 'internal_warehouse':
                print("\n\n--- Skipping Warehouse logic: Company set to External Warehouse ---\n\n")
                continue
            task = rec.task_id if hasattr(rec, 'task_id') else rec

            rec.status = 'waiting_warehouse_manager'
            if rec.part_id:
                rec.part_id.status = 'waiting_warehouse_manager'
                rec.message_post(
                    body=f"SuperVisor Approve request and send approval request for Warehouse Manager {self.env.user.name}. Status moved to Waiting Warehouse Manager.",
                    message_type='comment'
                )
                task.message_post(
                    body=f"SuperVisor Approve request and send approval request for Warehouse Manager {self.env.user.name}. Status moved to Waiting Warehouse Manager.",
                    message_type='comment'
                )

            print("\n\n========== Warehouse Manager Request Triggered ==========")
            print("Task Name:", task.name)
            print("Customer:", task.partner_id.name)
            print("Assignee:", task.user_ids.mapped('name') if task.user_ids else "No Assignee")

            # Get the actual product record
            product = task.customer_product_id.product_id if task.customer_product_id else False
            if not product:
                raise UserError(_("No product found for this task."))
            print(f"Customer product: {product.display_name} (ID: {product.id})")

            customer = task.partner_id
            if not customer:
                raise UserError(_("No customer linked with this task."))
            # Fetch location from stock.move.line for that product
            move_line = self.env['stock.move.line'].search([
                ('product_id', '=', product.id),
                '|',
                ('picking_id.partner_id', '=', customer.id),
                ('picking_id.partner_id.commercial_partner_id', '=', customer.commercial_partner_id.id)
            ], limit=1)

            if not move_line:
                print("No stock.move.line found for this product. Using default warehouse.")
                warehouse = self.env['stock.warehouse'].search([], limit=1)
            else:
                location = move_line.location_id
                print("Found location:", location.display_name)

                # Find warehouse linked to that location
                warehouse = self.env['stock.warehouse'].search([
                    ('lot_stock_id', '=', location.id),
                ], limit=1)

                if not warehouse:
                    # Try to find parent location hierarchy
                    print("No direct warehouse found for location. Checking parent locations...")
                    parent_location = location
                    while parent_location and not warehouse:
                        parent_location = parent_location.location_id
                        if parent_location:
                            warehouse = self.env['stock.warehouse'].search([
                                '|',
                                ('lot_stock_id', '=', parent_location.id),
                                ('view_location_id', '=', parent_location.id)
                            ], limit=1)
                    if warehouse:
                        print("Found warehouse via parent location:", warehouse.display_name)

            print("Detected Warehouse:", warehouse.display_name if warehouse else "No warehouse found")

            if not warehouse:
                raise UserError(_("Warehouse not found for product: %s") % product.display_name)

            # Find warehouse manager (field name 'manager')
            manager_user = warehouse.manager
            print("Warehouse Manager:", manager_user.name if manager_user else "No manager assigned")


            supervisor = task.department_id.manager_id if task.department_id else False
            current_user = self.env.user
            # Access control: Only Supervisor can approve
            if not supervisor or not supervisor.user_id:
                raise AccessError(_("No supervisor is assigned to this task, approval cannot proceed."))

            if current_user.id != supervisor.user_id.id:
                raise AccessError(
                    _("You are not allowed to approve this request. Only the Supervisor (%s) can approve this part request.")
                    % supervisor.name)

            part_name = rec.part_id.product_id.display_name or rec.part_id.display_name or rec.part_name or _("Unnamed Part")
            print("part name:", part_name)
            if not manager_user:
                raise UserError(_("No manager assigned to warehouse: %s") % warehouse.name)

            # Prepare notification message
            message_body = _(
                "Supervisor %s has sent an approval request for the part %s are available or not."
            ) % (self.env.user.name, part_name)

            print("Notification Body:", message_body)

            # Send notification to Warehouse Manager
            rec.message_notify(
                body=message_body,
                subject=f"Warehouse Manager Request - {rec.display_name}",
                record_name=rec.display_name,
                partner_ids=[warehouse.manager.user_id.partner_id.id],
                subtype_xmlid='mail.mt_comment',
            )
            print("Notification sent to Warehouse Manager:", manager_user.name)

            print("==========================================================\n\n")


    def action_part_available(self):
        """Move to next stage (shipment) and notify users"""
        for rec in self:

            if rec.company_id.enable_warehouse != 'internal_warehouse':
                print("\n\n--- Skipping Warehouse logic: Company set to External Warehouse ---\n\n")
                continue

            print("========== Action Part Available Triggered ==========")
            print(f"Record ID: {rec.id}, Name: {rec.display_name}")
            print(f"Current User: {self.env.user.name}")

            task = rec.task_id if hasattr(rec, 'task_id') else rec

            # Restrict supervisor from clicking
            # Get the actual product record
            product = task.customer_product_id.product_id if task.customer_product_id else False
            if not product:
                raise UserError(_("No product found for this task."))
            print(f"Customer product: {product.display_name} (ID: {product.id})")

            customer = task.partner_id
            if not customer:
                raise UserError(_("No customer linked with this task."))
            # Fetch location from stock.move.line for that product
            move_line = self.env['stock.move.line'].search([
                ('product_id', '=', product.id),
                '|',
                ('picking_id.partner_id', '=', customer.id),
                ('picking_id.partner_id.commercial_partner_id', '=', customer.commercial_partner_id.id)
            ], limit=1)

            if not move_line:
                print("No stock.move.line found for this product. Using default warehouse.")
                warehouse = self.env['stock.warehouse'].search([], limit=1)
            else:
                location = move_line.location_id
                print("Found location:", location.display_name)

                # Find warehouse linked to that location
                warehouse = self.env['stock.warehouse'].search([
                    ('lot_stock_id', '=', location.id),
                ], limit=1)

                if not warehouse:
                    # Try to find parent location hierarchy
                    print("No direct warehouse found for location. Checking parent locations...")
                    parent_location = location
                    while parent_location and not warehouse:
                        parent_location = parent_location.location_id
                        if parent_location:
                            warehouse = self.env['stock.warehouse'].search([
                                '|',
                                ('lot_stock_id', '=', parent_location.id),
                                ('view_location_id', '=', parent_location.id)
                            ], limit=1)
                    if warehouse:
                        print("Found warehouse via parent location:", warehouse.display_name)

            print("Detected Warehouse:", warehouse.display_name if warehouse else "No warehouse found")

            if not warehouse:
                raise UserError(_("Warehouse not found for product: %s") % product.display_name)

            # Get the current logged-in user
            current_user = self.env.user
            manager_employee = warehouse.manager
            manager_user = manager_employee.user_id if manager_employee else False

            print("Warehouse Manager (Employee):", manager_employee.name if manager_employee else "None")
            print("Manager Linked User:", manager_user.name if manager_user else "None",
                  manager_user.id if manager_user else "None")
            print("Logged-in User:", current_user.name, current_user.id)

            # Restrict access: Only warehouse manager's linked user can act
            if not manager_user or current_user.id != manager_user.id:
                raise AccessError(_(
                    "Only the Warehouse Manager (%s) can mark this part as available."
                ) % (manager_employee.name if manager_employee else "Not Assigned"))

            if rec.status == 'waiting_warehouse_manager':
                rec.status = 'shipment'
                rec.part_id.status = 'shipment'
                rec.message_post(
                    body=f"Part marked as available by {self.env.user.name}. Status moved to Shipment.",
                    message_type='comment'
                )
                task.message_post(
                    body=f"Part marked as available by {self.env.user.name}. Status moved to Shipment.",
                    message_type='comment'
                )

                # Collect users to notify
                notify_users = set()
                if rec.supervisor_id and rec.supervisor_id.user_id:
                    notify_users.add(rec.supervisor_id.user_id.id)
                if rec.user_ids:
                    notify_users.update(rec.user_ids.ids)

                print(f"Users to notify: {notify_users}")
                part_name = rec.part_id.product_id.display_name or rec.part_id.display_name or rec.part_name or _(
                    "Unnamed Part")
                print("part name:", part_name)
                # Send notifications
                if notify_users:
                    rec.message_notify(
                        subject=_("Part Available"),
                        body=_(
                            f"The product %s of the part %s has been marked as available for the task %s by %s."
                        ) % (
                        product.display_name,
                        part_name,
                        task.display_name,
                        self.env.user.display_name,
                    ),
                        partner_ids=[
                            user.partner_id.id
                            for user in rec.env['res.users'].browse(list(notify_users))
                            if user.partner_id
                        ],
                        subtype_xmlid='mail.mt_comment',
                        email_layout_xmlid='mail.mail_notification_light',
                        record_name=rec.display_name,
                    )
                    print("message_notify() executed successfully.")
                else:
                    print("No users found to notify.")
            else:
                print(f"Record not in 'waiting_warehouse_manager' stage, current status: {rec.status}")

            print("===============================================")

    def action_pick_up(self):
        """Only assigned users can mark part as Pick Up and notify supervisor"""
        for rec in self:
            if rec.company_id.enable_warehouse != 'internal_warehouse':
                print("\n\n--- Skipping Warehouse logic: Company set to External Warehouse ---\n\n")
                continue
            # Check company flag
            if not rec.company_id.enable_direct_pickup:
                raise UserError(_("Direct pickup is disabled for this company."))

            print("========== Action Pick Up Triggered ==========")
            print(f"Record ID: {rec.id}, Name: {rec.display_name}")
            print(f"Current User: {self.env.user.name}")
            print(f"Current Status: {rec.status}")
            task = rec.task_id if hasattr(rec, 'task_id') else rec

            # ✅ Only assigned user can click
            allowed_users = rec.user_ids.mapped('id')
            if self.env.user.id not in allowed_users:
                raise AccessError(_("Only assigned users can mark this part as picked up."))

            # ✅ Check stage
            if rec.status != 'shipment':
                raise UserError(_("You can only mark parts as Pick Up when status is 'Shipment'."))

            # ✅ Change status
            rec.status = 'pick_up'
            rec.part_id.status = 'pick_up'
            assigned_user_names = ', '.join(rec.user_ids.mapped('name')) or 'Unknown User'
            message_body = f"Part Pick Up by {assigned_user_names}. Status moved to Pick Up."
            rec.message_post(
                body=message_body,
                message_type='comment'
            )
            task.message_post(
                body=message_body,
                message_type='comment'
            )
            print(f"Status updated to 'pick_up' for record {rec.display_name}")

            # Notify supervisor
            notify_users = set()
            if rec.supervisor_id and rec.supervisor_id.user_id:
                notify_users.add(rec.supervisor_id.user_id.id)

            print(f"Supervisor to notify: {notify_users}")
            part_name = rec.part_id.product_id.display_name or rec.part_id.display_name or rec.part_name or _(
                "Unnamed Part")
            print("part name:", part_name)

            if notify_users:
                rec.message_notify(
                    subject=_("Part Picked Up"),
                    body=_(
                        f"The part '{rec.display_name}' has been marked as picked up by {self.env.user.name, part_name}."
                    ),
                    partner_ids=[
                        user.partner_id.id
                        for user in rec.env['res.users'].browse(list(notify_users))
                        if user.partner_id
                    ],
                    subtype_xmlid='mail.mt_comment',
                    email_layout_xmlid='mail.mail_notification_light',
                    record_name=rec.display_name,
                )
                print("📨 message_notify() sent successfully.")
            else:
                print("⚠️ No supervisor found to notify.")

            print("===============================================")

    def action_redirect_stock(self):
        self.ensure_one()
        company = self.env.company

        if company.enable_warehouse != 'internal_warehouse':
            return
        StockMoveLine = self.env['stock.move.line']

        if not self.product_id:
            raise UserError("No product linked with this record.")

        move_lines = StockMoveLine.search([('product_id', '=', self.product_id.id)])
        if self.partner_id:
            move_lines = move_lines.filtered(lambda m: m.picking_id.partner_id == self.partner_id)

        location_ids = move_lines.mapped('location_id.id')
        if not location_ids:
            raise UserError("No matching stock locations found for this product and partner.")

        # ✅ Create a custom quant action dynamically with saved context
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Stock View (Filtered)',
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('location_id', 'in', location_ids)],
            'context': {
                'default_location_ids': location_ids,
                'search_default_location_id': location_ids[0] if len(location_ids) == 1 else False,
            }
        }
        return action


class PartCustomerApprovalNotification(models.Model):
    _name = 'part.customer.approval.notification'
    _description = 'Customer Part Approval Notification'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    task_id = fields.Many2one('project.task', string='Call Name', readonly=True, store=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True, store=True)
    part_id = fields.Many2one('project.task.part', string='Part', readonly=True, store=True)
    part_name = fields.Char(string='Part Name', readonly=True, store=True)
    coverage = fields.Selection([
        ('foc', 'FOC'),
        ('chargeable', 'Chargeable')
    ], string='Coverage', readonly=True, store=True)
    message = fields.Text(string='Notification Message', store=True)
    sequence_fsm = fields.Char(string='Ticket Number', related='task_id.sequence_fsm', store=True)
    user_ids = fields.Many2many('res.users',string="Assignee")
    stage = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', string='Stage', tracking=True, readonly=True, store=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('waiting_warehouse_manager', 'Waiting Warehouse Manager'),
        ('shipment', 'Shipment'),
        ('pick_up', 'Pick up'),
        ('received', 'Received'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    def action_approve(self):
        for rec in self:
            rec.stage = 'approved'

            # Update the related part's stage to 'approved'
            if rec.part_id:
                rec.part_id.status = 'approved'

    def action_reject(self):
        for rec in self:
            rec.stage = 'rejected'

            # Update the related part's stage back to 'draft' when rejected
            if rec.part_id:
                rec.part_id.status = 'rejected'
