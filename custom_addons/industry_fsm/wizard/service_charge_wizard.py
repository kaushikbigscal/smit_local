from odoo import models, fields, api
from odoo.exceptions import UserError


class ServiceCallPaymentWizard(models.TransientModel):
    _name = "service.call.payment.wizard"
    _description = "Service Call Payment Wizard"

    task_id = fields.Many2one("project.task", string="Service Call", required=True)
    payment_date = fields.Datetime(string="Payment Date", default=fields.Datetime.now, readonly=True)
    total_charge = fields.Float(string="Total Charges", compute="_compute_total_charges", store=True, readonly=True)
    paid_amount = fields.Float(string="Already Paid", compute="_compute_paid_amount", store=True, readonly=True)
    remaining_amount = fields.Float(string="Remaining Amount", compute="_compute_remaining_amount", store=True,
                                    readonly=True)
    amount = fields.Float(string="Payment Amount", required=True)
    ref = fields.Char("Remark")
    payment_method_line_id = fields.Many2one("account.payment.method.line", string="Payment Method", required=True,
                                             default=lambda self: self._default_payment_method_line())
    journal_id = fields.Many2one('account.journal', string="Journal", default=lambda self: self._default_journal())
    last_payment_datetime = fields.Datetime(string="Last Payment DateTime", compute="_compute_last_payment")
    last_payment_amount = fields.Float(string="Last Payment Amount", compute="_compute_last_payment")
    payment_ids = fields.One2many("account.payment", "task_id", string="Payment History",
                                  compute="_compute_payment_history", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        task_id = self.env.context.get('default_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)
            total = sum(task.service_charge_ids.mapped('amount'))
            paid = sum(self.env['account.payment'].search([
                ('task_id', '=', task.id),
                ('state', '=', 'posted')
            ]).mapped('amount'))
            res['amount'] = total - paid
        return res

    @api.depends("task_id", "payment_ids", "payment_ids.write_date", "payment_ids.amount")
    def _compute_last_payment(self):
        for record in self:
            if record.task_id:
                latest_payment = self.env["account.payment"].search([
                    ("task_id", "=", record.task_id.id),
                    ("state", "=", "posted")
                ], order="write_date desc", limit=1)

                record.last_payment_datetime = latest_payment.write_date if latest_payment else False
                record.last_payment_amount = latest_payment.amount if latest_payment else 0.0
            else:
                record.last_payment_datetime = False
                record.last_payment_amount = 0.0

    @api.depends("task_id")
    def _compute_payment_history(self):
        """Fetch all posted payments related to the task and show in tree view."""
        for record in self:
            if record.task_id:
                record.payment_ids = self.env["account.payment"].search([
                    ("task_id", "=", record.task_id.id),
                    ("state", "=", "posted")
                ])
            else:
                record.payment_ids = False

    @api.model
    def _default_journal(self):
        return self.env['account.journal'].search([('name', '=', 'Service Call')], limit=1).id

    @api.depends("task_id")
    def _compute_total_charges(self):
        for task in self:
            task.total_charge = sum(task.task_id.service_charge_ids.mapped("amount"))

    @api.depends("task_id")
    def _compute_paid_amount(self):
        for task in self:
            payments = self.env["account.payment"].search([
                ("task_id", "=", task.task_id.id),
                ("state", "=", "posted")
            ])
            task.paid_amount = sum(payments.mapped("amount"))

    @api.depends("total_charge", "paid_amount")
    def _compute_remaining_amount(self):
        for task in self:
            task.remaining_amount = (task.total_charge or 0) - (task.paid_amount or 0)

    @api.model
    def _default_payment_method_line(self):
        journal = self._default_journal()
        if journal:
            payment_method = self.env["account.payment.method.line"].search([
                ('journal_id', '=', journal)
            ], limit=1)
            return payment_method.id if payment_method else False
        return False

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        """Update payment method based on selected journal."""
        if self.journal_id:
            payment_method = self.env["account.payment.method.line"].search([
                ("journal_id", "=", self.journal_id.id)
            ], limit=1)
            self.payment_method_line_id = payment_method.id if payment_method else False

    def action_register_payment(self):
        if self.remaining_amount == 0:
            raise UserError("This service call has already been paid in full.")
        if self.amount > self.remaining_amount or self.amount == 0:
            raise UserError(f"Payment amount ({self.amount}) cannot exceed remaining amount({self.remaining_amount}).")

        payment_vals = {
            "partner_id": self.task_id.partner_id.id,
            "amount": self.amount,
            "journal_id": self.journal_id.id,
            "payment_type": "inbound",
            "payment_method_line_id": self.payment_method_line_id.id,
            "task_id": self.task_id.id,
            "ref": self.ref or "",
        }

        payment = self.env["account.payment"].create(payment_vals)
        payment.action_post()
        journal_entry = payment.move_id
        if journal_entry:
            self.task_id.journal_entry_id = journal_entry.id
        self.task_id._compute_paid_amount()
        self.task_id._compute_remaining_amount()
        self.task_id._compute_payment_status()
        self._compute_last_payment()
        self._compute_payment_history()

        return {"type": "ir.actions.act_window_close"}
