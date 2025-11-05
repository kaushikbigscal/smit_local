# -*- coding: utf-8 -*-
import base64
from ast import literal_eval
from collections import defaultdict
from datetime import date, datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from pytz import timezone, UTC
import logging

_logger = logging.getLogger(__name__)


class FSMSignReportWizard(models.TransientModel):
    _name = 'fsm.sign.report.wizard'
    _description = 'Sign Report Wizard'

    report_signature = fields.Binary('Signature', copy=False, attachment=True)
    report_signed_by = fields.Char('Signed By', copy=False)

    def action_sign(self):
        active_id = self.env.context.get('active_id')
        report = self.env['project.task'].browse(active_id)  # Replace with your actual model
        if report:
            report.write({
                'report_signature': self.report_signature,
                'report_signed_by': self.report_signed_by,
            })
        return {'type': 'ir.actions.act_window_close'}


class Task(models.Model):
    _inherit = "project.task"

    allow_material = fields.Boolean(related='project_id.allow_material')
    allow_quotations = fields.Boolean(related='project_id.allow_quotations')
    quotation_count = fields.Integer(compute='_compute_quotation_count')
    material_line_product_count = fields.Integer(compute='_compute_material_line_totals')
    material_line_total_price = fields.Float(compute='_compute_material_line_totals')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', compute_sudo=True)
    display_create_invoice_primary = fields.Boolean(compute='_compute_display_create_invoice_buttons')
    display_create_invoice_secondary = fields.Boolean(compute='_compute_display_create_invoice_buttons')
    invoice_status = fields.Selection(related='sale_order_id.invoice_status')
    warning_message = fields.Char('Warning Message', compute='_compute_warning_message')
    invoice_count = fields.Integer("Number of invoices", related='sale_order_id.invoice_count')
    pricelist_id = fields.Many2one('product.pricelist', compute="_compute_pricelist_id")

    # Project Sharing fields
    portal_quotation_count = fields.Integer(compute='_compute_portal_quotation_count')
    portal_invoice_count = fields.Integer('Invoice Count', compute='_compute_portal_invoice_count')

    sale_line_id = fields.Many2one('sale.order.line', domain="""[
        '|', '|', ('order_partner_id', 'child_of', partner_id if partner_id else []), ('order_id.partner_shipping_id', 'child_of', partner_id if partner_id else []),
             '|', ('order_partner_id', '=?', partner_id), ('order_id.partner_shipping_id', '=?', partner_id),
               ('is_service', '=', True), ('is_expense', '=', False), ('state', '=', 'sale')
    ]""")

    # ---------------------------------------------------------------------------------------

    customer_product_id = fields.Many2one(
        'customer.product.mapping',
        string="Product",
        domain="[('customer_id', '=', partner_id)]",
        tracking=True
    )

    product_brand = fields.Char(related='customer_product_id.product_brand', string='Product Brand', readonly=True)
    product_model = fields.Char(related='customer_product_id.product_model', string='Product Model', readonly=True)

    available_serial_numbers = fields.Many2many(
        'stock.lot',
        string="Available Serial Numbers",
        compute='_compute_available_serial_numbers',
        store=False
    )

    product_category = fields.Many2one(
        'product.category', string='Product Category',
        related='customer_product_id.product_category',
        store=True
    )

    serial_number = fields.Many2one(
        'stock.lot',
        string="Serial Numbers",
        domain="[('id', 'in', available_serial_numbers)]",

        store=True
    )

    # unit_status = fields.Selection([
    #     ('amc', 'AMC'), ('chargeable', 'Chargeable'), ('free', 'Free'), ('warranty', 'Warranty')
    # ], string='Unit Status', tracking=True, readonly=True, store=True, compute='_compute_unit_status')

    unit_status = fields.Selection(selection=lambda self: self.env['call.type'].get_unit_status_selection(),
                                   string='Unit Status', tracking=True, readonly=True, store=True,
                                   compute='_compute_unit_status')

    # @api.onchange('unit_status')
    # def _onchange_unit_status(self):
    #     if self.unit_status in ['amc', 'chargeable', 'free', 'warranty']:
    #         self.call_type = self.unit_status
    #     else:
    #         self.call_type = False
    # @api.onchange('unit_status')
    # def _onchange_unit_status(self):
    #     xmlid_map = {
    #         'amc': 'industry_fsm.call_type_amc',
    #         'chargeable': 'industry_fsm.call_type_chargeable',
    #         'free': 'industry_fsm.call_type_free',
    #         'warranty': 'industry_fsm.call_type_warranty',
    #     }
    #     for rec in self:
    #         xmlid = xmlid_map.get(rec.unit_status)
    #         call_type = xmlid and rec.env.ref(xmlid, raise_if_not_found=False) or False
    #         if not call_type and rec.unit_status:
    #             call_type = rec.env['call.type'].search([('name', 'ilike', rec.unit_status)], limit=1)
    #         rec.call_type = call_type or False

    @api.onchange('unit_status')
    def _onchange_unit_status(self):
        for rec in self:
            call_type = False
            if rec.unit_status:
                # direct match on the stable code
                call_type = rec.env['call.type'].search([('code', '=', rec.unit_status)], limit=1)

                # fallback: if not found by code, try fuzzy match on name
                if not call_type:
                    call_type = rec.env['call.type'].search([('name', 'ilike', rec.unit_status)], limit=1)

            rec.call_type = call_type or False

    @api.depends('customer_product_id')
    def _compute_unit_status(self):
        for rec in self:
            rec.unit_status = rec.customer_product_id.status if rec.customer_product_id else False

    @api.onchange('customer_product_id')
    def _onchange_customer_product_id(self):
        if self.customer_product_id:
            # self.unit_status = self.customer_product_id.status
            self.serial_number = self.customer_product_id.serial_number_ids
        else:
            # self.unit_status = False
            self.serial_number = False

    @api.depends('customer_product_id')
    def _compute_available_serial_numbers(self):
        for rec in self:
            rec.available_serial_numbers = rec.customer_product_id.serial_number_ids if rec.customer_product_id else False

    def action_open_customer_product_mapping(self):
        return {
            'name': 'Customer Product Mapping',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.product.mapping',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.partner_id.id
            }
        }

    call_coordinator_id = fields.Many2one(
        'res.partner',
        string="Call Coordinator",
        domain="[('id', 'in', available_contacts), ('parent_id', '=', partner_id)]", tracking=True
    )
    available_contacts = fields.Many2many(
        'res.partner',
        compute="_compute_available_contacts",
        store=False
    )

    call_coordinator_phone = fields.Char(
        string="Call Coordinator Phone",
        compute="_compute_call_coordinator_phone",
        inverse='_inverse_call_coordinator_phone',
        store=True, copy=False, tracking=True
    )

    task_phone_update = fields.Boolean(compute='_compute_task_phone_update')

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

    @api.depends('partner_id')
    def _onchange_partner_id(self):
        """
        When the customer is selected, fetch the customer's contact (Call Coordinator).
        """
        for task in self:
            if task.partner_id:
                # Fetch the customer's contact (Call Coordinator)
                task.call_coordinator_id = task.partner_id.call_coordinator_id
            else:
                task.call_coordinator_id = False

    @api.depends('call_coordinator_id.phone', 'call_coordinator_id.mobile')
    def _compute_call_coordinator_phone(self):
        """Compute the phone number based on selected Call Coordinator."""
        for task in self:
            phone = filter(None,
                           [task.call_coordinator_id.phone, task.call_coordinator_id.mobile])  # Remove empty values
            task.call_coordinator_phone = ','.join(phone) if phone else False  # Join phone & mobile

    def _inverse_call_coordinator_phone(self):
        for task in self:
            task.call_coordinator_id.mobile = task.call_coordinator_phone or False

    @api.depends('call_coordinator_phone', 'call_coordinator_id.phone', 'call_coordinator_id.mobile')
    def _compute_task_phone_update(self):
        for task in self:
            combined_phones = ','.join(
                filter(None, [task.call_coordinator_id.phone, task.call_coordinator_id.mobile]))  # Match format
            task.task_phone_update = task.call_coordinator_phone != combined_phones

    @api.constrains('call_coordinator_id', 'call_coordinator_phone')
    def _check_call_coordinator_phone(self):
        for record in self:
            if not record.call_coordinator_id and record.call_coordinator_phone:
                raise ValidationError(
                    "You cannot set a Call Coordinator Phone without selecting a Call Coordinator."
                )

    report_signature = fields.Binary('Signature', copy=False, attachment=True)
    report_signed_by = fields.Char('Signed By', copy=False)
    fsm_is_sent = fields.Boolean('Is Report sent', readonly=True, copy=False)

    def action_sign_report_wizard(self):
        complete_timesheets = self.timesheet_ids.filtered(lambda t: t.unit_amount)
        if not complete_timesheets:
            raise ValidationError(
                _("You must have at least one timesheet entry to sign the report."))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sign Report',
            'res_model': 'fsm.sign.report.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('industry_fsm_sale.view_fsm_sign_report_wizard').id,
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def field_service_custom_report(self):
        self.ensure_one()
        try:
            report = None
            customizer = None
            # Use the first complaint type if multiple are selected
            complaint_type = self.complaint_type_id and self.complaint_type_id[0] or False
            # 1. If complaint type and report_id (ir.actions.report) is set, use it
            if complaint_type and complaint_type.report_id:
                if complaint_type.report_id._name == 'ir.actions.report':
                    report = complaint_type.report_id
            # 2. If not, try to find a customizer template (xml.upload) by file name
            if not report and complaint_type and complaint_type.report_id:
                file_name = complaint_type.report_id.name
                customizer = self.env['xml.upload'].sudo().search([
                    ('model_id.model', 'ilike', 'project.task'),
                    ('name', 'ilike', file_name),
                    ('xml_file', '!=', False),
                ], limit=1)
                if customizer:
                    # Use or create a unique QWeb view for this customizer
                    view = customizer.get_or_create_customizer_view()
                    # Create or get a report action for this view
                    report = self.env['ir.actions.report'].search([
                        ('report_name', '=', view.key),
                        ('model', '=', 'project.task'),
                    ], limit=1)
                    if not report:
                        report = self.env['ir.actions.report'].create({
                            'name': f'Custom Service Call Report {customizer.name}',
                            'model': 'project.task',
                            'report_type': 'qweb-pdf',
                            'report_name': view.key,
                            'report_file': view.key,
                        })
            # 3. Fallback to default
            if not report:
                report = self.env.ref('industry_fsm_sale.action_custom_report_field_service')
        except Exception:
            report = self.env.ref('industry_fsm_sale.action_custom_report_field_service')

        # Generate and attach report
        pdf_content, _ = report._render_qweb_pdf(report.report_name, res_ids=self.ids)
        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}_report.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        self.message_post(
            body="Custom Service Call Report generated.",
            attachment_ids=[attachment.id],
        )

        return report.report_action(self)

    def action_print_item_receipt(self):
        return self.env.ref('industry_fsm_sale.action_report_item_receipt').report_action(self)

    def _get_dynamic_field_values(self):

        user_tz = self.env.user.tz or 'UTC'
        field_model = self.env['item.receipt.field']
        fields_to_show = field_model.search([('show_in_report', '=', True)])
        for task in self:
            values = {}
            for field in fields_to_show:
                raw_value = getattr(task, field.name, '')
                value = raw_value

                # Handle relational fields (many2one, many2many)
                if isinstance(raw_value, models.Model):
                    if len(raw_value) > 1:
                        value = ", ".join(raw_value.mapped('name'))
                    elif len(raw_value) == 1:
                        value = raw_value.name
                    else:
                        value = ''


                # Handle datetime or date fields
                elif isinstance(raw_value, (date, datetime)):
                    field_def = task._fields.get(field.name)
                    if isinstance(raw_value, datetime) and field_def and field_def.type == 'datetime':
                        value = UTC.localize(raw_value).astimezone(timezone(user_tz)).strftime('%d-%m-%Y %H:%M:%S')
                    else:
                        value = raw_value.strftime('%d-%m-%Y')


                # Handle selection fields
                else:
                    field_def = task._fields.get(field.name)
                    if field_def and field_def.type == 'selection':
                        value = dict(field_def.selection).get(raw_value, raw_value)

                values[field.field_label or field.name] = value

            task.dynamic_field_values = values

    dynamic_field_values = fields.Json(compute='_compute_dynamic_field_values', store=False)

    @api.depends('fix_description')  # Add fields that might affect the values
    def _compute_dynamic_field_values(self):
        self._get_dynamic_field_values()

    def action_send_field_service_report(self):
        complete_timesheets = self.timesheet_ids.filtered(lambda t: t.unit_amount)
        if not complete_timesheets:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _("There are no reports to send."),
                    'sticky': False,
                    'type': 'danger',
                }
            }

        template_id = self.env.ref('industry_fsm_sale.mail_template_fsm_report').id
        self.message_subscribe(partner_ids=complete_timesheets.partner_id.ids)
        return {
            'name': _("Send report"),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_composition_mode': 'mass_mail' if len(complete_timesheets.ids) > 1 else 'comment',
                'default_model': 'project.task',
                'default_res_ids': complete_timesheets.ids,
                'default_template_id': template_id,
                'fsm_mark_as_sent': True,
                'mailing_document_based': True,
            },
        }

    def _message_post_after_hook(self, message, msg_vals):
        if self.env.context.get('fsm_mark_as_sent') and not self.fsm_is_sent:
            self.fsm_is_sent = True
        return super()._message_post_after_hook(message, msg_vals)

    def action_call_partner(self):
        self.ensure_one()
        phone = self.call_coordinator_id.mobile or self.call_coordinator_id.phone or self.partner_id.mobile or self.partner_id.phone
        if not phone:
            raise UserError("No phone number available for this customer")
        return {
            'type': 'ir.actions.client',
            'tag': 'call_partner_action',
            'params': {
                'phone': phone,
            },
        }

    # custom code completed----------------

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS | {'allow_material',
                                               'allow_quotations',
                                               'portal_quotation_count',
                                               'material_line_product_count',
                                               'material_line_total_price',
                                               'currency_id',
                                               'portal_invoice_count',
                                               'warning_message'}

    @api.depends('sale_order_id.pricelist_id', 'partner_id.property_product_pricelist')
    def _compute_pricelist_id(self):
        pricelist_active = self.user_has_groups('product.group_product_pricelist')
        for task in self:
            task.pricelist_id = pricelist_active and \
                                (task.sale_order_id.pricelist_id or task.partner_id.property_product_pricelist)

    @api.depends('pricelist_id', 'company_id')
    def _compute_currency_id(self):
        for task in self:
            task.currency_id = task.pricelist_id.currency_id or task.company_id.currency_id

    @api.depends('allow_material', 'material_line_product_count')
    def _compute_display_conditions_count(self):
        super(Task, self)._compute_display_conditions_count()
        for task in self:
            enabled = task.display_enabled_conditions_count
            satisfied = task.display_satisfied_conditions_count
            enabled += 1 if task.allow_material else 0
            satisfied += 1 if task.allow_material and task.material_line_product_count else 0
            task.update({
                'display_enabled_conditions_count': enabled,
                'display_satisfied_conditions_count': satisfied
            })

    def _compute_quotation_count(self):
        quotation_data = self.sudo().env['sale.order']._read_group([('task_id', 'in', self.ids)], ['task_id'],
                                                                   ['__count'])
        mapped_data = {task.id: count for task, count in quotation_data}
        for task in self:
            task.quotation_count = mapped_data.get(task.id, 0)

    def _compute_portal_quotation_count(self):
        domain = [('task_id', 'in', self.ids)]
        if self.user_has_groups('base.group_portal'):
            domain = expression.AND([domain, [('state', '!=', 'draft')]])
        quotation_data = self.env['sale.order']._read_group(domain, ['task_id'], ['__count'])
        mapped_data = {task.id: count for task, count in quotation_data}
        for task in self:
            task.portal_quotation_count = mapped_data.get(task.id, 0)

    @api.depends('sale_order_id.order_line.product_uom_qty', 'sale_order_id.order_line.price_total')
    def _compute_material_line_totals(self):
        def if_fsm_material_line(sale_line_id, task, employee_mapping_product_ids=None):
            is_not_timesheet_line = sale_line_id.product_id != task.timesheet_product_id
            if employee_mapping_product_ids:  # Then we need to search the product in the employee mappings
                is_not_timesheet_line = is_not_timesheet_line and sale_line_id.product_id.id not in employee_mapping_product_ids
            is_not_empty = sale_line_id.product_uom_qty != 0
            is_not_service_from_so = sale_line_id != task.sale_line_id
            is_task_related = sale_line_id.task_id == (task or task._origin)
            return all([is_not_timesheet_line, is_not_empty, is_not_service_from_so, is_task_related])

        employee_mapping_read_group = self.env['project.sale.line.employee.map'].sudo()._read_group(
            [('project_id', 'in', self.filtered('is_fsm').project_id.ids)],
            ['project_id'],
            ['timesheet_product_id:array_agg'],
        )
        employee_mapping_timesheet_product_ids = {project.id: timesheet_product_ids for project, timesheet_product_ids
                                                  in employee_mapping_read_group}
        sols = self.env['sale.order.line'].sudo().search([('order_id', 'in', self.sudo().sale_order_id.ids)])
        sols_by_so = defaultdict(lambda: self.env['sale.order.line'])
        for sol in sols:
            sols_by_so[sol.order_id.id] |= sol
        for task in self:
            material_sale_lines = sols_by_so[task.sudo().sale_order_id.id].sudo().filtered(
                lambda sol: if_fsm_material_line(sol, task,
                                                 employee_mapping_timesheet_product_ids.get(task.project_id.id)))
            task.material_line_total_price = sum(material_sale_lines.mapped('price_total'))
            task.material_line_product_count = round(sum(material_sale_lines.mapped('product_uom_qty')))

    @api.depends(
        'is_fsm', 'fsm_done', 'allow_billable',
        'task_to_invoice', 'invoice_status')
    # 'timer_start',
    def _compute_display_create_invoice_buttons(self):
        for task in self:
            primary, secondary = True, True
            # or task.timer_start
            if not task.is_fsm or not task.fsm_done or not task.allow_billable or \
                    not task.sale_order_id or task.invoice_status == 'invoiced' or \
                    task.sale_order_id.state in ['cancel']:
                primary, secondary = False, False
            else:
                if task.invoice_status in ['upselling', 'to invoice']:
                    secondary = False
                elif task.invoice_count > 0 and task.invoice_status == 'no':
                    secondary = False
                    primary = False
                else:  # Means invoice status is 'Nothing to Invoice'
                    primary = False
            task.update({
                'display_create_invoice_primary': primary,
                'display_create_invoice_secondary': secondary,
            })

    @api.depends('sale_line_id')
    def _compute_warning_message(self):
        employee_rate_fsm_tasks = self.filtered(lambda task:
                                                task.pricing_type == 'employee_rate'
                                                and task.sale_line_id
                                                and task.timesheet_ids
                                                and task.fsm_done)
        for task in employee_rate_fsm_tasks:
            if task.sale_line_id.order_id != task._origin.sale_line_id.order_id:
                task.warning_message = _(
                    'By saving this change, all timesheet entries will be linked to the selected Sales Order Item without distinction.')
            else:
                task.warning_message = False
        (self - employee_rate_fsm_tasks).update({'warning_message': False})

    @api.depends_context('uid')
    @api.depends('sale_order_id.invoice_ids')
    def _compute_portal_invoice_count(self):
        """ The goal of portal_invoice_count field is to show the Invoices stat button in Project sharing feature. """
        is_portal_user = self.user_has_groups('base.group_portal')
        invoices_by_so = {}
        available_invoices = False
        if is_portal_user:
            sale_orders_sudo = self.sale_order_id.sudo()
            invoices_by_so = {so.id: set(so.invoice_ids.ids) for so in sale_orders_sudo}
            available_invoices = set(
                self.env['account.move'].search([('id', 'in', sale_orders_sudo.invoice_ids.ids)]).ids)
        for task in self:
            task.portal_invoice_count = len(invoices_by_so.get(task.sale_order_id.id, set()).intersection(
                available_invoices)) if is_portal_user else task.invoice_count

    def _compute_sale_order_id(self):
        fsm_tasks = self.filtered('is_fsm')
        fsm_task_to_sale_order = {task.id: task.sale_order_id for task in fsm_tasks}
        super(Task, self)._compute_sale_order_id()
        for task in fsm_tasks:
            if task.sale_order_id:
                continue

            sale_order_id = fsm_task_to_sale_order.get(task.id, False)
            # the super call will remove the sale order from the task,
            # if the partner on the task is not the same as the partner on the sale order.
            # But for fsm tasks, the partner on the task could be the delivery address,
            # so we redo the integrity check but with the shipping partner in mind
            if sale_order_id and task.partner_id.commercial_partner_id in (
                    sale_order_id.partner_id.commercial_partner_id +
                    sale_order_id.partner_shipping_id.commercial_partner_id):
                task.sale_order_id = sale_order_id

    def action_create_invoice(self):
        # ensure the SO exists before invoicing, then confirm it
        so_to_confirm = self.filtered(
            lambda task: task.sale_order_id and task.sale_order_id.state in ['draft', 'sent']
        ).mapped('sale_order_id')
        so_to_confirm.action_confirm()

        # redirect create invoice wizard (of the Sales Order)
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_view_sale_advance_payment_inv")
        context = literal_eval(action.get('context', "{}"))
        so_task_mapping = defaultdict(list)
        for task in self:
            if task.sale_order_id:
                # As the key is anyway stringified in the JS, we casted the key here to make it clear.
                so_task_mapping[str(task.sale_order_id.id)].append(task.id)
        context.update({
            'active_id': self.sale_order_id.id if len(self) == 1 else False,
            'active_ids': self.mapped('sale_order_id').ids,
            'industry_fsm_message_post_task_id': so_task_mapping,
        })
        action['context'] = context
        return action

    def _get_last_sol_of_customer(self):
        self.ensure_one()
        # For FSM task, we don't want to search the last SOL of the customer.
        if self.is_fsm:
            return False
        return super(Task, self)._get_last_sol_of_customer()

    def _show_time_and_material(self):
        # check time and material section should visible or not in portal
        return self.allow_material and self.allow_billable and self.sale_order_id and self.is_fsm

    def action_view_invoices(self):
        invoices = self.mapped('sale_order_id.invoice_ids')
        # prevent view with onboarding banner
        list_view = self.env.ref('account.view_move_tree')
        kanban_view = self.env.ref('account.view_account_move_kanban')
        form_view = self.env.ref('account.view_move_form')
        if len(invoices) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoice'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'views': [[form_view.id, 'form']],
                'res_id': invoices.id,
                'context': {
                    'create': False,
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,kanban,form',
            'views': [[list_view.id, 'list'], [kanban_view.id, 'kanban'], [form_view.id, 'form']],
            'domain': [('id', 'in', invoices.ids)],
            'context': {
                'create': False,
            }
        }

    def action_project_sharing_view_invoices(self):
        """ Action used only in project sharing feature """
        return {
            "name": "Portal Invoices",
            "type": "ir.actions.act_url",
            "url":
                self.env['account.move'].search([('id', 'in', self.sale_order_id.sudo().invoice_ids.ids)],
                                                limit=1).get_portal_url()
                if self.portal_invoice_count == 1
                else f"/my/projects/{self.project_id.id}/task/{self.id}/invoices",
        }

    def action_fsm_create_quotation(self):
        view_form_id = self.env.ref('sale.view_order_form').id
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        action.update({
            'views': [(view_form_id, 'form')],
            'view_mode': 'form',
            'name': self.name,
            'context': {
                'fsm_mode': True,
                'default_partner_id': self.partner_id.id,
                'default_task_id': self.id,
                'default_company_id': self.company_id.id or self.env.company.id,
                'default_origin': f'{self.project_id.name} - {self.name}',
            },
        })
        return action

    def action_fsm_view_quotations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        action.update({
            'name': self.name,
            'domain': [('task_id', '=', self.id)],
            'context': {
                'fsm_mode': True,
                'default_task_id': self.id,
                'default_partner_id': self.partner_id.id},
        })
        if self.quotation_count == 1:
            action['res_id'] = self.env['sale.order'].search([('task_id', '=', self.id)]).id
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
        return action

    def action_project_sharing_view_quotations(self):
        """ Action used only in project sharing feature """
        self.ensure_one()
        return {
            "name": "Portal Quotations",
            "type": "ir.actions.act_url",
            "url":
                self.env['sale.order'].search([('task_id', '=', self.id)], limit=1).get_portal_url()
                if self.portal_quotation_count == 1
                else f"/my/projects/{self.project_id.id}/task/{self.id}/quotes",
        }

    def action_fsm_view_material(self):
        if not self.partner_id:
            raise UserError(_('A customer should be set on the task to generate a worksheet.'))

        self = self.with_company(self.company_id)

        domain = [
            ('company_id', 'in', [self.company_id.id, False]),
            ('sale_ok', '=', True),
            '|', ('detailed_type', 'in', ['consu', 'product']),
            '&', '&',
            ('detailed_type', '=', 'service'),
            ('invoice_policy', '=', 'delivery'),
            ('service_type', '=', 'manual'),
        ]
        if self.project_id and self.timesheet_product_id:
            domain = expression.AND([domain, [('id', '!=', self.timesheet_product_id.id)]])
        deposit_product = self.company_id.sale_down_payment_product_id
        if deposit_product:
            domain = expression.AND([domain, [('id', '!=', deposit_product.id)]])

        kanban_view = self.env.ref('industry_fsm_sale.industry_fsm_sale_product_catalog_kanban_view')
        search_view = self.env.ref('industry_fsm_sale.industry_fsm_sale_product_catalog_inherit_search_view')

        return {
            'type': 'ir.actions.act_window',
            'name': _('Choose Products'),
            'res_model': 'product.product',
            'views': [(kanban_view.id, 'kanban'), (False, 'form')],
            'search_view_id': [search_view.id, 'search'],
            'domain': domain,
            'context': {
                'fsm_mode': True,
                'create': self.env['product.template'].check_access_rights('create', raise_exception=False),
                'fsm_task_id': self.id,  # avoid 'default_' context key as we are going to create SOL with this context
                'pricelist': self.partner_id.property_product_pricelist.id,
                'order_id': self.sale_order_id.id,
                **self.sale_order_id.sudo()._get_action_add_from_catalog_extra_context(),
                'hide_qty_buttons': self.sale_order_id.sudo().locked,
                'default_invoice_policy': 'delivery',
            },
            'help': _("""<p class="o_view_nocontent_smiling_face">
                                No products found. Let's create one!
                            </p><p>
                                Keep track of the products you are using to complete your tasks, and invoice your customers for the goods.
                                Tip: using kits, you can add multiple products at once.
                            </p><p>
                                When your task is marked as done, your stock will be updated automatically. Simply choose a warehouse
                                in your profile from where to draw stock.
                            </p>""")
        }

    def _fsm_ensure_sale_order(self):
        """ get the SO of the task. If no one, create it and return it """
        self.ensure_one()
        if not self.sale_order_id:
            self._fsm_create_sale_order()
        return self.sale_order_id

    def _fsm_create_sale_order(self):
        """ Create the SO from the task, with the 'service product' sales line and link all timesheet to that line it """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('A customer should be set on the task to generate a worksheet.'))

        SaleOrder = self.env['sale.order']
        if self.user_has_groups('project.group_project_user'):
            SaleOrder = SaleOrder.sudo()

        user_id = self.user_ids[0] if self.user_ids else self.env['res.users']
        team = self.env['crm.team'].sudo()._get_default_team_id(user_id=user_id.id, domain=None)
        sale_order = SaleOrder.create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'analytic_account_id': self._get_task_analytic_account_id().id,
            'team_id': team.id if team else False,
            'origin': f'{self.project_id.name} - {self.name}',
        })
        # update after creation since onchange_partner_id sets the current user
        sale_order.user_id = user_id.id

        self.sale_order_id = sale_order

    def _fsm_create_sale_order_line(self):
        """ Generate sales order item based on the pricing_type on the project and the timesheets in the current task

            When the pricing_type = 'employee_rate', we need to search the employee mappings for the employee who timesheeted
            in the current task to retrieve the product in each mapping and generate an SOL for this product with the total
            hours of the related timesheet(s) as the ordered quantity. Some SOLs can be already generated if the user manually
            adds the SOL in the task or when he adds some materials in the tasks, a SO is generated.
            If the user manually adds in the SO some service products, we must check in these before generating new one.
            When no SOL is linked to the task before marking this task as done and no existing SOLs correspond to the default
            product in the project, we take the first SOL generated if no generated SOL contain the default product of the project.
            Here are the steps realized for this case:
                1) Get all timesheets in the tasks
                2) Classify this timesheets by employee
                3) Search the employee mappings (project.sale.line.employee.map model or the sale_line_employee_ids field in the
                   project model) for the employee who timesheets to have the product linked to the employee.
                4) Use the dict created in the second step to classify the timesheets in another dict in which the key is the id
                   and the price_unit of the product and the id uom. This information is important for the generation of the SOL.
                5) if no SOL is linked in the task then we add the default service project defined in the project into the dict
                   created in the previous step and value is the remaining timesheets.
                   That is, the ones are no impacted in the employee mappings (sale_line_employee_ids field) defined in the project.
                6) Classify the existing SOLs of the SO linked to the task, because the SO can be generated before the user clicks
                   on 'mark as done' button, for instance, when the user adds materials for this task. A dict is created containing
                   the id and price_unit of the product as key and the SOL(s) containing this product.
                    6.1) If no SOL is linked, then we check in the existing SOLs if there is a SOL with the default product defined
                        in the product, if it is the case then the SOL will be linked to the task.
                        This step can be useless if the user doesn't manually add a service product in the SO. In fact, this step
                        searchs in the SOLs of the SO, if there is an SOL with the default service product defined in the project.
                        If it is the case then the SOL will be linked to the task.
                7) foreach in the dict created in the step 4, in this loop, first of all, we search in the dict containing the
                   existing SOLs if the id of the product is containing in an existing SOL. If yes then, we don't generate an SOL
                   and link it to the timesheets linked to this product. Otherwise, we generate the SOL with the information containing
                   in the key and the timesheets containing in the value of the dict for this key.

            When the pricing_type = 'task_rate', we generate a sales order item with product_uom_qty is equal to the total hours of timesheets in the task.
            Once the SOL is generated we link this one to the task and its timesheets.
        """
        self.ensure_one()
        # Get all timesheets in the current task (step 1)
        not_billed_timesheets = self.env['account.analytic.line'].sudo().search(
            [('task_id', '=', self.id), ('project_id', '!=', False), ('is_so_line_edited', '=', False)]).filtered(
            lambda t: t._is_not_billed())
        if self.pricing_type == 'employee_rate':
            # classify these timesheets by employee (step 2)
            timesheets_by_employee_dict = defaultdict(
                lambda: self.env['account.analytic.line'])  # key: employee_id, value: timesheets
            for timesheet in not_billed_timesheets:
                timesheets_by_employee_dict[timesheet.employee_id.id] |= timesheet

            # Search the employee mappings for the employees whose timesheets in the task (step 3)
            employee_mappings = self.env['project.sale.line.employee.map'].search([
                ('employee_id', 'in', list(timesheets_by_employee_dict.keys())),
                ('timesheet_product_id', '!=', False),
                ('project_id', '=', self.project_id.id)])

            # Classify the timesheets by product (step 4)
            product_timesheets_dict = defaultdict(lambda: self.env[
                'account.analytic.line'])  # key: (timesheet_product_id.id, price_unit, uom_id.id), value: list of timesheets
            for mapping in employee_mappings:
                employee_timesheets = timesheets_by_employee_dict[mapping.employee_id.id]
                product_timesheets_dict[
                    mapping.timesheet_product_id.id, mapping.price_unit, mapping.timesheet_product_id.uom_id.id] |= employee_timesheets
                not_billed_timesheets -= employee_timesheets  # we remove the timesheets because are linked to the mapping

            product = self.env['product.product']
            sol_in_task = bool(self.sale_line_id)
            if not sol_in_task:  # Then, add the default product of the project and remaining timesheets in the dict (step 5)
                default_product = self.project_id.timesheet_product_id
                if not_billed_timesheets:
                    # The remaining timesheets must be added in the sol with the default product defined in the fsm project
                    # if there is not SOL in the task
                    product = default_product
                    product_timesheets_dict[product.id, product.lst_price, product.uom_id.id] |= not_billed_timesheets
                elif (
                        default_product.id, default_product.lst_price,
                        default_product.uom_id.id) in product_timesheets_dict:
                    product = default_product

            # Get all existing service sales order items in the sales order (step 6)
            existing_service_sols = self.sudo().sale_order_id.order_line.filtered('is_service')
            sols_by_product_and_price_dict = defaultdict(
                lambda: self.env['sale.order.line'])  # key: (product_id, price_unit), value: sales order items
            for sol in existing_service_sols:  # classify the SOLs to easily find the ones that we want.
                sols_by_product_and_price_dict[sol.product_id.id, sol.price_unit] |= sol

            task_values = defaultdict()  # values to update the current task
            update_timesheet_commands = []  # used to update the so_line field of each timesheet in the current task.

            if not sol_in_task and sols_by_product_and_price_dict:  # Then check in the existing sol if a SOL has the default product defined in the project to set the SOL of the task (step 6.1)
                sol = sols_by_product_and_price_dict.get(
                    (self.project_id.timesheet_product_id.id, self.project_id.timesheet_product_id.lst_price))
                if sol:
                    task_values['sale_line_id'] = sol.id
                    sol_in_task = True

            for (timesheet_product_id, price_unit, uom_id), timesheets in product_timesheets_dict.items():
                sol = sols_by_product_and_price_dict.get((timesheet_product_id,
                                                          price_unit))  # get the existing SOL with the product and the correct price unit
                if not sol:  # Then we create it
                    sol = self.env['sale.order.line'].sudo().create({
                        'order_id': self.sale_order_id.id,
                        'product_id': timesheet_product_id,
                        'price_unit': price_unit,
                        # The project and the task are given to prevent the SOL to create a new project or task based on the config of the product.
                        'project_id': self.project_id.id,
                        'task_id': self.id,
                        'product_uom_qty': sum(timesheets.mapped('unit_amount')),
                        'product_uom': uom_id,
                    })

                # Link the SOL to the timesheets
                update_timesheet_commands.extend(
                    [fields.Command.update(timesheet.id, {'so_line': sol.id}) for timesheet in timesheets if
                     not timesheet.is_so_line_edited])
                if not sol_in_task and (
                        not product or (product.id == timesheet_product_id and product.lst_price == price_unit)):
                    # If there is no sol in task and the product variable is empty then we give the first sol in this loop to the task
                    # However, if the product is not empty then we search the sol with the same product and unit price to give to the current task
                    task_values['sale_line_id'] = sol.id
                    sol_in_task = True

            if update_timesheet_commands:
                task_values['timesheet_ids'] = update_timesheet_commands

            self.sudo().write(task_values)
        elif not self.sale_line_id:
            # Check if there is a SOL containing the default product of the project before to create a new one.
            sale_order_line = self.sale_order_id and self.sudo().sale_order_id.order_line.filtered(
                lambda sol: sol.product_id == self.project_id.timesheet_product_id)[:1]
            if not sale_order_line:
                sale_order_line = self.env['sale.order.line'].sudo().create({
                    'order_id': self.sale_order_id.id,
                    'product_id': self.timesheet_product_id.id,
                    # The project and the task are given to prevent the SOL to create a new project or task based on the config of the product.
                    'project_id': self.project_id.id,
                    'task_id': self.id,
                    'product_uom_qty': sum(timesheet_id.unit_amount for timesheet_id in not_billed_timesheets),
                })
            self.sudo().write({  # We need to sudo in case the user cannot see all timesheets in the current task.
                'sale_line_id': sale_order_line.id,
                # assign SOL to timesheets
                'timesheet_ids': [fields.Command.update(timesheet.id, {'so_line': sale_order_line.id}) for timesheet in
                                  not_billed_timesheets if not timesheet.is_so_line_edited]
            })

    def _prepare_materials_delivery(self):
        # While industry_fsm_stock is not installed then we automatically deliver materials
        read_group_timesheets = self.env['account.analytic.line'].sudo().search_read(
            [('task_id', 'in', self.ids), ('project_id', '!=', False), ('so_line', '!=', False)], ['so_line'])
        timesheet_sol_ids = [timesheet['so_line'][0] for timesheet in read_group_timesheets]
        sale_order_lines = self.env['sale.order.line'].sudo().search([
            ('id', 'not in', timesheet_sol_ids),
            ('task_id', 'in', self.ids),
            ('order_id', 'in', self.sale_order_id.sudo().filtered(lambda so: so.state == 'sale').ids),
        ])
        for sol in sale_order_lines:
            sol.qty_delivered = sol.product_uom_qty

    class ProjectTaskRecurrence(models.Model):
        _inherit = 'project.task.recurrence'

        def _get_sale_line_id(self, task):
            if not task.is_fsm:
                return super()._get_sale_line_id(task)
            return False
