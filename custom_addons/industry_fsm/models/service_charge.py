from odoo import models, fields, _, api
from odoo.tools import format_datetime


class ServiceChargeType(models.Model):
    _name = 'service.charge'
    _description = 'Service Charge'

    task_id = fields.Many2one('project.task', string="Service Call", tracking=True)
    service_charge_type = fields.Many2one("service.charge.type", string='Service Charge Type', required=True,
                                          tracking=True)
    amount = fields.Float(string="Charge")
    paid = fields.Float(string="Paid")
    status = fields.Selection([("paid", "Paid"), ("notpaid", "Not Paid"), ("partially paid", "Partially Paid")])
    # call_type = fields.Selection(
    #     selection=[('warranty', 'Warranty'), ('amc', 'AMC'), ('chargeable', 'Chargeable'), ('free', 'Free'),
    #                ('project', 'Project')],
    #     string="Call Type",
    #     readonly=False
    # )
    call_type = fields.Many2one(
        comodel_name='call.type',
        string="Call Type",
        readonly=False
    )

    def unlink(self):
        tasks = self.mapped("task_id")
        for charge in self:
            service_charge_name = charge.service_charge_type.service_charge_type if charge.service_charge_type else "Unknown"
            deleted_time = format_datetime(self.env, fields.Datetime.now(), tz=self.env.user.tz)
            if charge.task_id:
                message = _(
                    "Service Charge '%s' of amount %s has been deleted on %s."
                ) % (service_charge_name, charge.amount, deleted_time)
                charge.task_id.message_post(body=message, subtype_xmlid="mail.mt_note")
        res = super().unlink()
        for task in tasks:
            task._compute_total_charge()
            task._compute_paid_amount()
            task._compute_remaining_amount()
            task._compute_payment_status()
            if not task.service_charge_ids:
                self.env["account.payment"].search([("task_id", "=", task.id)]).unlink()
                task.payment_status = "notpaid"
                task.message_post(body=_("All service charges removed. Payments history cleared."))
                if task.journal_entry_id and task.journal_entry_id.state == 'posted':
                    task.journal_entry_id.button_draft()
                    task.message_post(body=_("Linked invoice reverted to draft."), subject="Invoice Updated")
        return res


class AccountPayment(models.Model):
    _inherit = "account.payment"

    task_id = fields.Many2one("project.task", string="Related Service Call")

    def unlink(self):
        tasks = self.mapped('task_id')
        res = super().unlink()
        # recompute status after payment deletion
        tasks._compute_paid_amount()
        tasks._compute_remaining_amount()
        tasks._compute_payment_status()
        return res

    def open_payment_form(self):
        self.ensure_one()
        if self.payment_ids:
            return {
                'name': 'Payment',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': self.payment_ids.id,
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_account_payment_form').id,
                'target': 'current',
            }
        return True

    @api.constrains('payment_method_line_id')
    def _check_payment_method_line_id(self):
        for pay in self:
            if pay.journal_id and pay.journal_id.name == "Service Call":
                continue


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    @api.model
    def create(self, vals):
        journal_id = vals.get("journal_id")
        if not journal_id:
            service_call_journal = self.env["account.journal"].search([
                ("name", "=", "Service Call")
            ], limit=1)

            if service_call_journal:
                journal_id = service_call_journal.id
                vals["journal_id"] = journal_id
            else:
                raise ValueError("Please select a journal or configure a 'Service Call' journal.")

        manual_payment_method = self.env["account.payment.method"].search([
            ("name", "=", "Manual")
        ], limit=1)

        if not manual_payment_method:
            manual_payment_method = self.env["account.payment.method"].create({
                "name": "Manual",
                "payment_type": "inbound",  # Adjust as needed
            })
        vals.update({
            "payment_method_id": manual_payment_method.id,
            "journal_id": journal_id,
        })
        return super().create(vals)
