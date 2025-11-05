from odoo import models, fields, api,_
from odoo.http import request


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    payment_required_first = fields.Boolean(
        string="Payment Required First",
        help="Check this if a pending request should be prioritized first."
    )

#
# class PartServiceWizard(models.TransientModel):
#     _inherit = 'part.service.wizard'
#
#     coverage = fields.Selection([
#         ('foc', 'FOC'),
#         ('chargeable', 'Chargeable')
#     ], string='Coverage', store=True)
#
#     amount = fields.Float(
#         string="Amount",
#     )
#
#     @api.model
#     def default_get(self, fields_list):
#         res = super().default_get(fields_list)
#         part_id = self._context.get('active_id')
#         if part_id:
#             part = self.env['project.task.part'].browse(part_id)
#             if 'coverage' in fields_list:
#                 res['coverage'] = part.coverage or 'chargeable'  # fallback if blank
#             if 'part_service_type' in fields_list:
#                 res['part_service_type'] = part.part_service_type
#             if 'amount' in fields_list:
#                 res['amount'] = part.amount
#         return res
#
#     def apply_service_update(self):
#         self.ensure_one()
#         self.part_id.write({
#             'part_service_type': self.part_service_type,
#             'serial_number_id': self.serial_number_id.id,
#             'previous_serial_number_id': self.previous_serial_number_ids.id,
#             'description': self.description,
#             'coverage': self.coverage,
#             'amount': self.amount,
#         })


class ContractType(models.Model):
    _inherit = 'contract.type'

    with_parts = fields.Boolean("With Parts")

#
# class ProjectTaskPart(models.Model):
#     _inherit = 'project.task.part'
#
#     coverage = fields.Selection([
#         ('foc', 'FOC'),
#         ('chargeable', 'Chargeable')
#     ], string='Coverage', compute='_compute_coverage', store=True)
#
#     amount = fields.Float(
#         string="Amount",
#         compute='_compute_amount',
#         store=True,
#         readonly=False
#     )
#
#     @api.depends('product_id')
#     def _compute_amount(self):
#         for rec in self:
#             if rec.product_id:
#                 rec.amount = rec.product_id.standard_price
#             else:
#                 rec.amount = 0.0
#
#     @api.depends(
#         'mapping_id',
#         'mapping_id.status',
#         'mapping_id.contract_id',
#         'mapping_id.contract_id.contract_type.with_parts',
#     )
#     def _compute_coverage(self):
#         for rec in self:
#             coverage = 'chargeable'
#             mapping = rec.mapping_id
#
#             if mapping:
#                 contract_type = mapping.contract_id.contract_type if mapping.contract_id else False
#
#                 if contract_type:
#                     contract_coverage = contract_type.with_parts
#                     if contract_coverage:
#                         coverage = 'foc'
#                     else:
#                         coverage = 'chargeable'
#
#                 elif mapping.status in ['warranty', 'extended_warranty']:
#                     coverage = 'foc'
#
#             rec.coverage = coverage
#
#     def action_check_availability(self):
#         """Send notification only to the department manager using message_post"""
#         for part in self:
#             print(f"\nProcessing part ID: {part.id}")
#
#             task = part.task_id
#             if not task:
#                 print("No task linked to this part, skipping...")
#                 continue
#             print(f"Task found: {task.id} - {task.name}")
#
#             # Get the department supervisor (manager)
#             supervisor = task.department_id.manager_id if task.department_id else False
#             if not supervisor or not supervisor.user_id:
#                 print("No supervisor or supervisor has no user linked, skipping...")
#                 continue
#             print(f"Supervisor found: {supervisor.name} (user: {supervisor.user_id.name})")
#
#             # Prepare message
#             part_name = part.product_id.display_name if part.product_id else 'Unknown Part'
#             customer = task.partner_id
#             print("customer name:",customer.name)
#             message = _("Part '%s' requires your approval.") % part_name
#             print(f"Message prepared: {message}")
#
#             # Create notification record in part.approval.notification
#             notification = self.env['part.approval.notification'].create({
#                 'task_id': task.id,
#                 'part_id': part.id,
#                 'part_name': part_name,
#                 'supervisor_id': supervisor.id,
#                 'user_ids': task.user_ids,
#                 'partner_id': customer.id,
#                 'product_id': task.customer_product_id.product_id.id if task.customer_product_id and task.customer_product_id.product_id else False,
#                 'coverage': part.coverage,
#                 'status': 'waiting_supervisor',
#             })
#             print(f"Notification record created: ID {notification.id}")
#
#             # Temporarily remove other followers to avoid extra notifications
#             existing_followers = task.message_follower_ids.mapped('partner_id')
#             print(f"Existing followers: {[p.name for p in existing_followers]}")
#             # Optionally: remove all followers except supervisor
#             # task.message_unsubscribe(partner_ids=[p.id for p in existing_followers if p != supervisor.user_id.partner_id])
#
#             # Post message to task chatter and notify only the supervisor
#             task.message_post(
#                 body=message,
#                 subject=_("Part Approval Required"),
#                 partner_ids=[supervisor.user_id.partner_id.id],
#                 message_type='comment',
#                 subtype_xmlid='mail.mt_comment',
#             )
#             print(f"Message posted to supervisor: {supervisor.name}")
#
#         print("action_check_availability finished.")
#         return True
#
#     def action_customer_approval(self):
#         print("Starting action_customer_approval")
#         for part in self:
#             print(f"\nProcessing part record id: {part.id}")
#             # Only allow if chargeable
#             if part.coverage != 'chargeable':
#                 print(f"Part coverage is '{part.coverage}', skipping (not chargeable)")
#                 continue
#             task = part.task_id
#             print(f"Linked task: {task.name if task else 'No task'}")
#             if not task or not task.partner_id:
#                 print("No task or partner linked to part, skipping...")
#                 continue
#             customer = task.partner_id
#             print(f"Customer partner: {customer.name} (id={customer.id})")
#             ticket_no = task.sequence_fsm or task.name
#             print(f"Ticket number: {ticket_no}")
#             part_name = part.product_id.display_name if part.product_id else 'Unknown Part'
#             print(f"Part display name: {part_name}")
#             product_name = (
#                 task.customer_product_id.product_id.display_name
#                 if task.customer_product_id and task.customer_product_id.product_id
#                 else 'No Product'
#             )
#             print(f"Customer product name: {product_name}")
#
#             subject = "Customer Approval Required"
#             msg = f"Customer approval requested for part '{part_name}' of product '{product_name}' in ticket {ticket_no}."
#             url = f"/my/ticket/{task.id}"
#
#             print(f"Notification subject: {subject}")
#             print(f"Notification message: {msg}")
#             print(f"Notification URL: {url}")
#
#             # Create notification record for internal tracking (USE SUDO)
#             notification_vals = self.env['part.customer.approval.notification'].create({
#                 'task_id': task.id,
#                 'product_id': task.customer_product_id.product_id.id if task.customer_product_id and task.customer_product_id.product_id else False,
#                 'part_id': part.id,
#                 'part_name': part_name,
#                 'coverage': part.coverage,
#                 'stage': 'pending',
#             })
#             print("Notification values prepared:", notification_vals)
#
#             # Send notification to customer
#             try:
#                 print(f"Attempting to send customer notification to partner: {customer.name}")
#                 task._send_customer_notification(
#                     partner=customer,
#                     subject=subject,
#                     message=msg,
#                     url=url
#                 )
#                 print(f"Customer notification sent successfully for part '{part_name}' in task '{task.name}'")
#             except Exception as e:
#                 print(f"Failed to send customer notification for task {task.id}: {str(e)}")
#
#         print("Completed action_customer_approval")
#         return True
#
# class PartApprovalNotification(models.Model):
#     _name = 'part.approval.notification'
#     _description = 'Part Approval Notification'
#     _rec_name = 'task_id'
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     task_id = fields.Many2one('project.task', string='Call Name', readonly=True)
#     # product_tmpl_id = fields.Many2one('product.template', string='Product')
#     product_id = fields.Many2one('product.product', string='Product', readonly=True)
#     part_id = fields.Many2one('project.task.part', string='Part', readonly=True)
#     user_ids = fields.Many2many('res.users',string="Assignee",readonly=True)
#     part_name = fields.Char(string='Part Name', readonly=True)  # human-readable part name
#     supervisor_id = fields.Many2one('hr.employee', string='Supervisor', readonly=True)
#     stage = fields.Selection([
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#     ], default='pending', string='Status', tracking=True, readonly=True)
#     message = fields.Text(string='Notification Message')
#     partner_id = fields.Many2one('res.partner', string='Customer')
#     coverage = fields.Selection([
#         ('foc', 'FOC'),
#         ('chargeable', 'Chargeable')
#     ], string='Coverage', readonly=True)
#
#     sequence_fsm = fields.Char(
#         string='Ticket Number',
#         related='task_id.sequence_fsm',
#         store=True,
#     )
#
#     status = fields.Selection([
#         ('draft', 'Draft'),
#         ('waiting_supervisor', 'Waiting Supervisor Approval'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#         ('waiting_for_customer_approval', 'Waiting For Customer Approval'),
#         ('ready','Ready'),
#         ('received','Received')
#     ], string='Status', default='draft',tracking=True)
#
#     def action_approve(self):
#         print("action_approve called")
#         for rec in self:
#             print(f"Approving notification id={rec.id}, part_name={rec.part_name}")
#             rec.status = 'approved'
#             rec.stage = 'approved'
#
#
#     def action_reject(self):
#         print("action_reject called")
#         for rec in self:
#             print(f"Rejecting notification id={rec.id}, part_name={rec.part_name}")
#             rec.status = 'rejected'
#             rec.stage = 'rejected'
#
# class PartCustomerApprovalNotification(models.Model):
#     _name = 'part.customer.approval.notification'
#     _description = 'Customer Part Approval Notification'
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     task_id = fields.Many2one('project.task', string='Call Name', readonly=True, store=True)
#     product_id = fields.Many2one('product.product', string='Product', readonly=True, store=True)
#     part_id = fields.Many2one('project.task.part', string='Part', readonly=True, store=True)
#     part_name = fields.Char(string='Part Name', readonly=True, store=True)
#     coverage = fields.Selection([
#         ('foc', 'FOC'),
#         ('chargeable', 'Chargeable')
#     ], string='Coverage', readonly=True, store=True)
#     message = fields.Text(string='Notification Message', store=True)
#     sequence_fsm = fields.Char(string='Ticket Number', related='task_id.sequence_fsm', store=True)
#     user_ids = fields.Many2many('res.users',string="Assignee")
#     stage = fields.Selection([
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#     ], default='pending', string='Stage', tracking=True, readonly=True, store=True)
#
#     status = fields.Selection([
#         ('waiting_for_customer_approval', 'Waiting For Customer Approval'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected')
#     ], default='waiting_for_customer_approval', string='Status', tracking=True, store=True)
#
#     def action_approve(self):
#         for rec in self:
#             rec.status = 'approved'
#             rec.stage = 'approved'
#
#     def action_reject(self):
#         for rec in self:
#             rec.status = 'rejected'
#             rec.stage = 'rejected'
