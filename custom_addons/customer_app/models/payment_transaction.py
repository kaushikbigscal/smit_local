# # -*- coding: utf-8 -*-
# import logging
# from odoo import api, fields, models
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#
#         # Capture old states before the write
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         # Only act if state turned to 'done'
#         for tx in self:
#             old = old_states.get(tx.id)
#             new = tx.state
#
#             if old not in ('done', 'authorized') and new in ('done', 'authorized'):
#                 journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                     ('company_id', '=', tx.company_id.id),
#                     ('type', 'in', ['bank', 'cash']),
#                 ], limit=1)
#
#                 for order in tx.sale_order_ids:
#                     try:
#                         # 1) Confirm quotation if still draft/sent
#                         if order.state in ('draft', 'sent'):
#                             order.with_context(send_email=False).action_confirm()
#                         # 2) Create invoice(s) from SO
#
#                         try:
#                             invoices = order._create_invoices()
#                         except UserError as e:
#                             # Only ignore "nothing to invoice" errors, re-raise others
#                             if "No items are available to invoice" in str(e):
#                                 invoices = self.env['account.move']  # empty recordset
#                                 _logger.info("SO %s has nothing to invoice. Skipping invoice creation.", order.name)
#                             else:
#                                 raise
#
#                         # 3) Post invoices
#                         invoices.action_post()
#
#                         # 4) Register payment on each invoice (up to the transaction amount)
#                         for inv in invoices:
#                             if inv.amount_residual <= 0:
#                                 continue
#
#                             # Compute amount to pay on this invoice from the transaction (handle currency)
#                             tx_amount_in_inv_currency = tx.currency_id._convert(
#                                 tx.amount, inv.currency_id, inv.company_id, fields.Date.context_today(self)
#                             ) if tx.currency_id and inv.currency_id and tx.currency_id != inv.currency_id else (
#                                         tx.amount or inv.amount_residual)
#
#                             amount_to_pay = min(inv.amount_residual, tx_amount_in_inv_currency or inv.amount_residual)
#
#                             # Use the standard wizard to register the payment to the invoice
#                             pay_reg = self.env['account.payment.register'].with_context(
#                                 active_model='account.move',
#                                 active_ids=inv.ids,
#                             ).create({
#                                 'payment_date': fields.Date.context_today(self),
#                                 'journal_id': journal.id if journal else False,
#                                 'amount': amount_to_pay,
#                             })
#
#                             payment_moves = pay_reg._create_payments()
#                             inv._compute_amount()  # refresh
#
#                     except Exception as e:
#                         _logger.exception("Failed processing SO %s", order.name)
#
#         return res

# # -*- coding: utf-8 -*-
# import logging
# from odoo import api, fields, models
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         for tx in self:
#             old = old_states.get(tx.id)
#             new = tx.state
#
#             if old not in ('done', 'authorized') and new in ('done', 'authorized'):
#                 journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                     ('company_id', '=', tx.company_id.id),
#                     ('type', 'in', ['bank', 'cash']),
#                 ], limit=1)
#
#                 for order in tx.sale_order_ids:
#                     try:
#                         _logger.info(">>> Processing SO: %s", order.name)
#                         if order.state in ('draft', 'sent'):
#                             order.with_context(send_email=False).action_confirm()
#                             _logger.info(">>> SO %s confirmed", order.name)
#
#                         try:
#                             invoices = order._create_invoices()
#                             _logger.info(">>> Invoice(s) created: %s", invoices.ids)
#                         except UserError as e:
#                             if "No items are available to invoice" in str(e):
#                                 invoices = self.env['account.move']
#                                 _logger.warning(">>> SO %s has nothing to invoice", order.name)
#                             else:
#                                 raise
#
#                         invoices.action_post()
#                         _logger.info(">>> Invoice(s) posted: %s", invoices.ids)
#
#                         for inv in invoices:
#                             _logger.info(">>> Processing Invoice %s with residual %.2f", inv.name, inv.amount_residual)
#
#                             if inv.amount_residual <= 0:
#                                 _logger.info(">>> Invoice %s already fully paid, skipping", inv.name)
#                                 continue
#
#                             # ---- NEW: Handle prepayment ----
#                             if order.require_payment and order.prepayment_percent:
#                                 prepay_amount = (order.amount_total * order.prepayment_percent) / 100.0
#                                 _logger.info(">>> Prepayment mode active: %s%% -> %.2f", order.prepayment_percent, prepay_amount)
#                                 tx_amount = prepay_amount
#                             else:
#                                 tx_amount = tx.amount
#                                 _logger.info(">>> Normal payment mode, tx_amount = %.2f", tx_amount)
#
#                             # Convert into invoice currency if needed
#                             if tx.currency_id and inv.currency_id and tx.currency_id != inv.currency_id:
#                                 tx_amount_in_inv_currency = tx.currency_id._convert(
#                                     tx_amount, inv.currency_id, inv.company_id, fields.Date.context_today(self)
#                                 )
#                             else:
#                                 tx_amount_in_inv_currency = tx_amount
#
#                             _logger.info(">>> tx_amount_in_inv_currency = %.2f", tx_amount_in_inv_currency)
#
#                             # Final amount to pay (do not exceed residual)
#                             amount_to_pay = min(inv.amount_residual, tx_amount_in_inv_currency)
#                             _logger.info(">>> Registering partial payment of %.2f on invoice %s", amount_to_pay, inv.name)
#
#                             pay_reg = self.env['account.payment.register'].with_context(
#                                 active_model='account.move',
#                                 active_ids=inv.ids,
#                             ).create({
#                                 'payment_date': fields.Date.context_today(self),
#                                 'journal_id': journal.id if journal else False,
#                                 'amount': amount_to_pay,
#                             })
#
#                             payment_moves = pay_reg._create_payments()
#                             inv._compute_amount()  # refresh totals
#                             _logger.info(">>> Payment moves created: %s", payment_moves.ids)
#
#                     except Exception as e:
#                         _logger.exception("Failed processing SO %s", order.name)
#
#         return res
#
# # -*- coding: utf-8 -*-
# import logging
# from odoo import api, fields, models
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         print(">>> WRITE called on payment.transaction ids=%s vals=%s", self.ids, vals)
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         for tx in self:
#             old_state = old_states.get(tx.id)
#             new_state = tx.state
#             print(">>> TX %s state changed %s → %s", tx.id, old_state, new_state)
#
#             # Trigger invoice creation when payment is authorized or done
#             if old_state not in ('done', 'authorized') and new_state in ('done', 'authorized'):
#                 print(">>> Payment finalized for tx=%s (state=%s)", tx.id, new_state)
#                 self._create_invoice_from_payment(tx)
#         return res
#
#     def _create_invoice_from_payment(self, tx):
#         print(">>> _create_invoice_from_payment called for tx=%s", tx.id)
#
#         # Use journal from payment provider or fallback
#         journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#             ('company_id', '=', tx.company_id.id),
#             ('type', 'in', ['bank', 'cash']),
#         ], limit=1)
#         print(">>> Using journal id=%s name=%s", journal.id if journal else None, journal.name if journal else None)
#
#         # Loop through related sale orders
#         for order in tx.sale_order_ids:
#             try:
#                 print(">>> Handling SO %s (state=%s)", order.name, order.state)
#
#                 # Confirm quotation if still draft or sent
#                 if order.state in ('draft', 'sent'):
#                     print(">>> Confirming quotation for SO %s", order.name)
#                     order.with_context(send_email=False).action_confirm()
#                     print(">>> SO confirmed: %s", order.name)
#
#                 # Create invoice normally (full amount)
#                 print(">>> Creating invoice for SO %s", order.name)
#                 invoices = order._create_invoices()
#                 if not invoices:
#                     print(">>> No invoice created for SO %s (nothing to invoice)", order.name)
#                     continue
#
#                 # Post invoices
#                 for inv in invoices:
#                     if not inv.invoice_line_ids:
#                         print(">>> Invoice %s has no lines, skipping", inv.name)
#                         continue
#
#                     print(">>> Posting invoice %s (total=%s)", inv.name, inv.amount_total)
#                     inv.action_post()
#                     print(">>> Invoice %s posted", inv.name)
#
#                     # Register payment **partial amount**
#                     if tx.amount > 0 and inv.amount_residual > 0:
#                         payment_amount = min(tx.amount, inv.amount_residual)
#                         print(">>> Registering payment %s on invoice %s (residual=%s)", payment_amount, inv.name, inv.amount_residual)
#                         pay_reg = self.env['account.payment.register'].with_context(
#                             active_model='account.move',
#                             active_ids=[inv.id],
#                         ).create({
#                             'payment_date': fields.Date.context_today(self),
#                             'journal_id': journal.id if journal else False,
#                             'amount': payment_amount,
#                         })
#                         payment_moves = pay_reg._create_payments()
#                         print(">>> Payment registered for invoice %s: %s", inv.name, payment_moves.ids)
#
#                     inv._compute_amount()
#                     print(">>> Invoice %s residual after payment: %s", inv.name, inv.amount_residual)
#
#             except Exception as e:
#                 print(">>> Failed processing SO %s", order.name)






# ============================ Correct Code ===========================================

# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def write(self, vals):
        _logger.info(">>> WRITE called on payment.transaction ids=%s vals=%s" % (self.ids, vals))
        old_states = {tx.id: tx.state for tx in self}
        res = super().write(vals)

        for tx in self:
            old_state = old_states.get(tx.id)
            new_state = tx.state
            _logger.info(">>> TX %s state changed %s → %s" % (tx.id, old_state, new_state))

            # Trigger invoice creation when payment is authorized or done
            if old_state not in ('done', 'authorized') and new_state in ('done', 'authorized'):
                _logger.info(">>> Payment finalized for tx=%s (state=%s)" % (tx.id, new_state))
                self._create_invoice_from_payment(tx)
        return res

    def _create_invoice_from_payment(self, tx):
        _logger.info(">>> _create_invoice_from_payment called for tx=%s" % tx.id)

        # Use journal from payment provider or fallback
        journal = tx.provider_id.journal_id or self.env['account.journal'].search([
            ('company_id', '=', tx.company_id.id),
            ('type', 'in', ['bank', 'cash']),
        ], limit=1)
        _logger.info(">>> Using journal id=%s name=%s" % (journal.id if journal else None, journal.name if journal else None))

        # Loop through related sale orders
        for order in tx.sale_order_ids:
            try:
                _logger.info(">>> Handling SO %s (state=%s)" % (order.name, order.state))

                # Confirm quotation if still draft or sent
                if order.state in ('draft', 'sent'):
                    _logger.info(">>> Confirming quotation for SO %s" % order.name)
                    order.with_context(send_email=False).action_confirm()
                    _logger.info(">>> SO confirmed: %s" % order.name)

                # Create invoice normally (full amount)
                _logger.info(">>> Creating invoice for SO %s" % order.name)
                invoices = order._create_invoices()
                if not invoices:
                    _logger.info(">>> No invoice created for SO %s (nothing to invoice)" % order.name)
                    continue

                # Post invoices
                for inv in invoices:
                    if not inv.invoice_line_ids:
                        _logger.info(">>> Invoice %s has no lines, skipping" % inv.name)
                        continue

                    _logger.info(">>> Posting invoice %s (total=%s)" % (inv.name, inv.amount_total))
                    inv.action_post()
                    _logger.info(">>> Invoice %s posted" % inv.name)

                # Instead of manually creating payments, just reconcile transaction
                _logger.info(">>> Reconciling transaction %s with invoices %s" % (tx.id, invoices.ids))
                tx._reconcile_after_done()

                # Debug residual amounts
                for inv in invoices:
                    inv._compute_amount()
                    _logger.info(">>> Invoice %s residual after reconcile: %s" % (inv.name, inv.amount_residual))

            except Exception as e:
                _logger.exception(">>> Failed processing SO %s" % order.name)





# Correct code
# -*- coding: utf-8 -*-
# import logging
# from odoo import api, fields, models
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         _logger.info("write() called on payment.transaction with vals:", vals)
#
#         # Capture old states before the write
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         # Only act if state turned to 'done'
#         for tx in self:
#             old = old_states.get(tx.id)
#             new = tx.state
#             _logger.info(f"tx.id={tx.id} ref={tx.reference} old_state={old} new_state={new}")
#
#             if old not in ('done', 'authorized') and new in ('done', 'authorized'):
#                 _logger.info(f"Transaction DONE detected → processing sale orders. tx={tx.reference}")
#                 journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                     ('company_id', '=', tx.company_id.id),
#                     ('type', 'in', ['bank', 'cash']),
#                 ], limit=1)
#                 _logger.info(f"Using journal id={journal.id} name={journal.name if journal else None}")
#
#                 for order in tx.sale_order_ids:
#                     try:
#                         _logger.info(f"Handling SO {order.name} (state={order.state})")
#
#                         # 1) Confirm quotation if still draft/sent
#                         if order.state in ('draft', 'sent'):
#                             _logger.info(f"Confirming quotation → SO for {order.name}")
#                             order.with_context(send_email=False).action_confirm()
#                             _logger.info(f"SO confirmed: {order.name}")
#
#                         # 2) Create full invoice(s) from SO
#                         _logger.info(f"Creating invoices for SO {order.name}")
#                         try:
#                             invoices = order._create_invoices()
#                         except UserError as e:
#                             if "No items are available to invoice" in str(e):
#                                 invoices = self.env['account.move']  # empty recordset
#                                 _logger.info("SO %s has nothing to invoice. Skipping invoice creation.", order.name)
#                             else:
#                                 raise
#
#                         # 3) Post invoices
#                         invoices.action_post()
#                         _logger.info(f"Invoices posted: {invoices.ids}")
#
#                         # 4) Register payment with only the transaction amount
#                         for inv in invoices:
#                             _logger.info(f"Processing payment for invoice {inv.name}, residual={inv.amount_residual}, tx.amount={tx.amount}")
#
#                             if inv.amount_residual <= 0:
#                                 _logger.info(f"Invoice {inv.name} already fully paid.")
#                                 continue
#
#                             # Convert payment amount if needed
#                             tx_amount_in_inv_currency = tx.currency_id._convert(
#                                 tx.amount, inv.currency_id, inv.company_id, fields.Date.context_today(self)
#                             ) if tx.currency_id and inv.currency_id and tx.currency_id != inv.currency_id else (tx.amount or inv.amount_residual)
#
#                             # Pay only the tx amount (not full invoice)
#                             amount_to_pay = min(inv.amount_residual, tx_amount_in_inv_currency)
#
#                             if amount_to_pay <= 0:
#                                 continue
#
#                             _logger.info(f"Registering payment amount={amount_to_pay} on {inv.name} via journal={journal and journal.name}")
#
#                             pay_reg = self.env['account.payment.register'].with_context(
#                                 active_model='account.move',
#                                 active_ids=inv.ids,
#                             ).create({
#                                 'payment_date': fields.Date.context_today(self),
#                                 'journal_id': journal.id if journal else False,
#                                 'amount': amount_to_pay,
#                             })
#
#                             payment_moves = pay_reg._create_payments()
#                             _logger.info(f"Payments created for {inv.name}: {payment_moves.ids}")
#
#                             inv._compute_amount()
#                             _logger.info(f"Invoice {inv.name} residual after payment: {inv.amount_residual}")
#
#                     except Exception as e:
#                         _logger.exception("Failed processing SO %s", order.name)
#
#         return res

# import logging
# from odoo import fields, models
#
# _logger = logging.getLogger(__name__)
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         _logger.info("write() called on payment.transaction with vals: %s", vals)
#
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         for tx in self:
#             old = old_states.get(tx.id)
#             new = tx.state
#             if old not in ('done', 'authorized') and new in ('done', 'authorized'):
#                 _logger.info(f"Transaction DONE detected → processing sale orders. tx={tx.reference}")
#
#                 # Journal
#                 journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                     ('company_id', '=', tx.company_id.id),
#                     ('type', 'in', ['bank', 'cash']),
#                 ], limit=1)
#
#                 for order in tx.sale_order_ids:
#                     try:
#                         if order.state in ('draft', 'sent'):
#                             order.with_context(send_email=False).action_confirm()
#
#                         # 1) Create full invoice (full sale order amount)
#                         invoice = order._create_invoices()
#                         invoice.action_post()
#
#                         # 2) Register payment (partial)
#                         pay_reg = self.env['account.payment.register'].with_context(
#                             active_model='account.move',
#                             active_ids=invoice.ids,
#                         ).create({
#                             'payment_date': fields.Date.context_today(self),
#                             'journal_id': journal.id if journal else False,
#                             'amount': tx.amount,  # partial payment
#                         })
#                         payment_moves = pay_reg._create_payments()
#
#                         # 3) Update sale order
#                         order.invoice_ids = [(4, inv.id) for inv in invoice]
#                         order.write({'state': 'sale'})
#                         if sum(invoice.mapped('amount_residual')) == 0:
#                             order.write({'invoice_status': 'invoiced'})
#                         else:
#                             order.write({'invoice_status': 'to invoice'})
#
#                         _logger.info(f"SO {order.name} updated with invoice {invoice.ids}, partial payment {tx.amount}")
#
#                     except Exception as e:
#                         _logger.exception("Failed processing SO %s", order.name)
#
#         return res
#

# # -*- coding: utf-8 -*-
# from odoo import api, fields, models, _
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     processed_for_invoice = fields.Boolean(
#         string='Invoice processed', default=False,
#         help='Technical flag to avoid double invoice/payment creation.'
#     )
#
#     def _set_authorized(self, **kwargs):
#         """When provider moves to 'authorized' we run our logic once."""
#         txs = super()._set_authorized(**kwargs)
#         self._process_invoices_and_payments()
#         return txs
#
#     def _set_done(self, **kwargs):
#         """When provider goes straight to 'done'."""
#         txs = super()._set_done(**kwargs)
#         self._process_invoices_and_payments()
#         return txs
#
#     def _process_invoices_and_payments(self):
#         """Create/reuse invoice & register payment once per transaction."""
#         for tx in self.filtered(lambda t: t.state in ('done', 'authorized') and not t.processed_for_invoice):
#             _logger.info("Processing invoice/payment for tx %s", tx.reference)
#
#             journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                 ('company_id', '=', tx.company_id.id),
#                 ('type', 'in', ['bank', 'cash']),
#             ], limit=1)
#
#             for order in tx.sale_order_ids:
#                 try:
#                     # Confirm order if needed
#                     if order.state in ('draft', 'sent'):
#                         order.with_context(send_email=False).action_confirm()
#
#                     # Create or reuse invoice
#                     invoice = order.invoice_ids.filtered(lambda inv: inv.state != 'cancel')[:1]
#                     if not invoice:
#                         invoice = order._create_invoices()
#                         invoice.action_post()
#                         _logger.info("Invoice %s created for order %s", invoice.id, order.name)
#                     else:
#                         _logger.info("Using existing invoice %s for order %s", invoice.id, order.name)
#
#                     # Register partial payment if not already registered
#                     if tx.amount > 0 and invoice.amount_residual > 0:
#                         already_paid = invoice.payment_ids.filtered(
#                             lambda p: abs(p.amount - tx.amount) < 0.01 and p.ref == tx.reference
#                         )
#                         if not already_paid:
#                             amount_to_pay = min(tx.amount, invoice.amount_residual)
#                             pay_reg = self.env['account.payment.register'].with_context(
#                                 active_model='account.move',
#                                 active_ids=invoice.ids,
#                             ).create({
#                                 'payment_date': fields.Date.context_today(self),
#                                 'journal_id': journal.id if journal else False,
#                                 'amount': amount_to_pay,
#                             })
#                             pay_reg._create_payments()
#                             _logger.info("Registered partial payment %.2f for invoice %s", amount_to_pay, invoice.id)
#                         else:
#                             _logger.info("Payment already registered for invoice %s, skipping", invoice.id)
#
#                     # Update SO invoice status
#                     order.write({'invoice_ids': [(4, invoice.id)], 'state': 'sale'})
#                     order.invoice_status = 'invoiced' if invoice.amount_residual == 0 else 'to invoice'
#
#                 except Exception:
#                     _logger.exception("Failed processing SO %s", order.name)
#
#             # Mark transaction processed so we don’t run again
#             tx.processed_for_invoice = True

# from odoo import models,api,fields
# from odoo.exceptions import UserError
#
#
# class SaleOrder(models.Model):
#     _inherit = "sale.order"
#
#     def _create_invoice_and_reconcile(self, payment_amount=None):
#         for order in self:
#             # 1️⃣ Create invoice if not exists
#             if not order.invoice_ids:
#                 invoice = order._create_invoices()
#                 invoice.action_post()
#             else:
#                 invoice = order.invoice_ids.filtered(lambda i: i.state != 'cancel')
#                 for inv in invoice.filtered(lambda i: i.state == 'draft'):
#                     inv.action_post()
#
#             if payment_amount:
#                 # 2️⃣ Create payment
#                 journal = self.env['account.journal'].search([
#                     ('type', '=', 'bank'),
#                     ('company_id', '=', order.company_id.id)
#                 ], limit=1)
#                 if not journal:
#                     raise UserError("No bank journal found!")
#
#                 payment = self.env['account.payment'].create({
#                     'partner_id': order.partner_id.id,
#                     'amount': payment_amount,
#                     'payment_type': 'inbound',
#                     'partner_type': 'customer',
#                     'journal_id': journal.id,
#                     'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
#                     'company_id': order.company_id.id,
#                 })
#
#                 # 3️⃣ Post payment
#                 payment.action_post()
#
#                 # 4️⃣ Reconcile with invoice receivable lines
#                 for inv in invoice:
#                     receivable_lines = inv.line_ids.filtered(
#                         lambda l: l.account_id.account_type == 'receivable' and l.partner_id == order.partner_id
#                     )
#                     payment_lines = payment.move_id.line_ids.filtered(
#                         lambda l: l.account_id.account_type == 'receivable'
#                     )
#
#                     for line in receivable_lines:
#                         line_to_reconcile = payment_lines.filtered(lambda pl: pl.account_id == line.account_id)
#                         if line_to_reconcile:
#                             line.reconcile(line_to_reconcile)
#
#                     # 5️⃣ Update payment_state
#                     if inv.amount_residual == 0:
#                         inv.payment_state = 'paid'
#                     elif inv.amount_residual < inv.amount_total:
#                         inv.payment_state = 'partial'
#                     else:
#                         inv.payment_state = 'not_paid'
#
#     def action_confirm(self):
#         res = super().action_confirm()
#         for order in self:
#             order._create_invoice_and_reconcile(payment_amount=order.amount_total / 2)
#         return res

# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def _has_to_be_paid(self):
#         self.ensure_one()
#         # allow payment if state is not 'paid' and last tx is pending/authorized
#         last_tx = self.get_portal_last_transaction()
#         if self.payment_state in ('not_paid', 'partial'):
#             return True
#         if last_tx and last_tx.state in ('pending','authorized'):
#             return True
#         return False


# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     created_from_portal = fields.Boolean(
#         string="Created from Portal",
#         help="Set to True when invoice is auto-created from a portal payment transaction."
#     )
