from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'


    # part_ids = fields.One2many(
    #     'project.task.part',
    #     'task_id',
    #     string="Parts"
    # )
    #
    # def write(self, vals):
    #     """Prevent moving to Resolved or Done if pending approval exists"""
    #     for task in self:
    #         if 'stage_id' in vals:
    #             new_stage = self.env['project.task.type'].browse(vals['stage_id'])
    #             if new_stage.name in ['Resolved', 'Done']:
    #                 # Check parts approval
    #                 if any(part.status in ['draft'] for part in task.part_ids):
    #                     raise UserError(
    #                         _("Part request pending. You cannot resolve or done this task until supervisor approval is done.")
    #                     )
    #     return super(ProjectTask, self).write(vals)

class PartServiceWizard(models.TransientModel):
    _inherit = 'part.service.wizard'

    coverage = fields.Selection([
        ('foc', 'FOC'),
        ('chargeable', 'Chargeable')
    ], string='Coverage', store=True)

    amount = fields.Float(
        string="Amount",
    )

    # stage = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('waiting_customer/supervisor', 'Waiting Customer/Supervisor'),
    #     ('approved', 'Approved'),
    #     ('rejected', 'Rejected'),
    #     ('completed', 'Completed'),
    # ])

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        part_id = self._context.get('active_id')
        if part_id:
            part = self.env['project.task.part'].browse(part_id)
            if 'coverage' in fields_list:
                res['coverage'] = part.coverage or 'chargeable'  # fallback if blank
            if 'part_service_type' in fields_list:
                res['part_service_type'] = part.part_service_type
            if 'amount' in fields_list:
                res['amount'] = part.amount
            # if 'stage' in fields_list:
            #     res['stage'] = part.stage or 'draft'
        return res

    def apply_service_update(self):
        self.ensure_one()
        self.part_id.write({
            'part_service_type': self.part_service_type,
            'serial_number_id': self.serial_number_id.id,
            'previous_serial_number_id': self.previous_serial_number_ids.id,
            'description': self.description,
            'coverage': self.coverage,
            'amount': self.amount,
            # 'stage': self.stage,
        })


class ProjectTaskPart(models.Model):
    _inherit = 'project.task.part'

    coverage = fields.Selection([
        ('foc', 'FOC'),
        ('chargeable', 'Chargeable')
    ], string='Coverage', compute='_compute_coverage', store=True, readonly=False)

    amount = fields.Float(
        string="Amount",
        compute='_compute_amount',
        store=True,
        readonly=False
    )
    # stage = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('waiting_customer/supervisor', 'Waiting Customer/Supervisor'),
    #     ('approved', 'Approved'),
    #     ('rejected', 'Rejected'),
    #     ('completed', 'Completed'),
    # ], required=True, default='draft', tracking=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('waiting_warehouse_manager', 'Waiting Warehouse Manager'),
        ('shipment', 'Shipment'),
        ('pick_up', 'Pick up'),
        ('received', 'Received'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    approval_requested = fields.Boolean(
        string='Approval Requested',
        default=False,
        help='Indicates if customer approval has been requested'
    )

    # @api.depends('product_id')
    # def _compute_amount(self):
    #     for rec in self:
    #         if rec.product_id:
    #             rec.amount = rec.product_id.standard_price
    #         else:
    #             rec.amount = 0.0
    @api.depends('product_id', 'coverage')
    def _compute_amount(self):
        for rec in self:
            if rec.coverage == 'foc':
                rec.amount = 0.0
            elif rec.product_id:
                rec.amount = rec.product_id.standard_price
            else:
                rec.amount = 0.0

    @api.depends(
        'mapping_id',
        # 'mapping_id.status',
        'mapping_id.contract_id',
        'mapping_id.contract_id.contract_type.with_parts',
    )
    def _compute_coverage(self):
        for rec in self:
            coverage = 'chargeable'
            mapping = rec.mapping_id

            if mapping:
                contract_type = mapping.contract_id.contract_type if mapping.contract_id else False

                if contract_type:
                    contract_coverage = contract_type.with_parts
                    if contract_coverage:
                        coverage = 'foc'
                    else:
                        coverage = 'chargeable'

                elif mapping.status != 'chargeable':
                    coverage = 'foc'

            rec.coverage = coverage

    def action_check_availability(self):
        """Send notification only to the department manager using message_post"""
        for part in self:
            print(f"\nProcessing part ID: {part.id}")

            task = part.task_id
            if not task:
                print("No task linked to this part, skipping...")
                continue
            print(f"Task found: {task.id} - {task.name}")

            # Get the department supervisor (manager)
            supervisor = task.department_id.manager_id if task.department_id else False
            if not supervisor or not supervisor.user_id:
                print("No supervisor or supervisor has no user linked, skipping...")
                continue
            print(f"Supervisor found: {supervisor.name} (user: {supervisor.user_id.name})")

            # Prepare message
            part_name = part.product_id.display_name if part.product_id else 'Unknown Part'
            customer = task.partner_id
            print("customer name:",customer.name)
            # message = _("Part '%s' requires your approval.") % part_name
            # print(f"Message prepared: {message}")
            product_name = (
                task.customer_product_id.product_id.display_name
                if task.customer_product_id and task.customer_product_id.product_id
                else 'No Product'
            )
            print(f"Customer product name to show: {product_name}")

            if supervisor.company_id != task.company_id:
                print(
                    f"Skipping: Supervisor ({supervisor.company_id.name}) and Task ({task.company_id.name}) belong to different companies.")
                continue

            # Create notification record in part.approval.notification
            notification = self.env['part.approval.notification'].create({
                'task_id': task.id,
                'part_id': part.id,
                'part_name': part_name,
                'supervisor_id': supervisor.id,
                'user_ids': task.user_ids,
                'partner_id': customer.id,
                'product_id': task.customer_product_id.product_id.id if task.customer_product_id and task.customer_product_id.product_id else False,
                'coverage': part.coverage,
                'status': 'draft',
                'company_id': task.company_id.id,
            })
            print(f"Notification record created: ID {notification.id}")


            # Post message to task chatter and notify only the supervisor
            notification.message_notify(
                body=f"The part '{part_name}' of product '{product_name}' is send approval for Task '{task.name}'.",
                subject=_("Part Approval Request"),
                partner_ids=[supervisor.user_id.partner_id.id],
                subtype_xmlid='mail.mt_comment',
            )
            task.message_post(
                body=f"The part '{part_name}' of product '{product_name}' is send approval for Task '{task.name}'.",
                subtype_xmlid = 'mail.mt_note',
            )
            print(f"Message posted to supervisor: {supervisor.name}")

        print("action_check_availability finished.")
        return True

    def action_customer_approval(self):
        print("Starting action_customer_approval")
        for part in self:
            print(f"\nProcessing part record id: {part.id}")
            part.approval_requested = True
            # Only allow if chargeable
            if part.coverage != 'chargeable':
                print(f"Part coverage is '{part.coverage}', skipping (not chargeable)")
                continue
            task = part.task_id
            print(f"Linked task: {task.name if task else 'No task'}")
            if not task or not task.partner_id:
                print("No task or partner linked to part, skipping...")
                continue
            customer = task.partner_id
            print(f"Customer partner: {customer.name} (id={customer.id})")
            ticket_no = task.sequence_fsm or task.name
            print(f"Ticket number: {ticket_no}")
            part_name = part.product_id.display_name if part.product_id else 'Unknown Part'
            print(f"Part display name: {part_name}")
            product_name = (
                task.customer_product_id.product_id.display_name
                if task.customer_product_id and task.customer_product_id.product_id
                else 'No Product'
            )
            print(f"Customer product name: {product_name}")

            subject = "Customer Approval Request"
            msg = f"Customer approval requested for part '{part_name}' of product '{product_name}' in ticket {ticket_no} / {task.name}."
            url = f"/my/ticket/{task.id}"

            print(f"Notification subject: {subject}")
            print(f"Notification message: {msg}")
            print(f"Notification URL: {url}")

            # Create notification record for internal tracking (USE SUDO)
            notification_vals = self.env['part.customer.approval.notification'].create({
                'task_id': task.id,
                'product_id': task.customer_product_id.product_id.id if task.customer_product_id and task.customer_product_id.product_id else False,
                'part_id': part.id,
                'part_name': part_name,
                'coverage': part.coverage,
                'stage': 'pending',
            })
            print("Notification values prepared:", notification_vals)

            # Send notification to customer
            try:
                print(f"Attempting to send customer notification to partner: {customer.name}")
                task._send_customer_notification(
                    partner=customer,
                    subject=subject,
                    message=msg,
                    url=url
                )
                print(f"Customer notification sent successfully for part '{part_name}' in task '{task.name}'")
            except Exception as e:
                print(f"Failed to send customer notification for task {task.id}: {str(e)}")
            task.message_post(
                body=f"Customer approval requested for part '{part_name}' of product '{product_name}' in ticket {ticket_no} / {task.name}.",
                subtype_xmlid='mail.mt_note',
            )

        print("Completed action_customer_approval")
        return True