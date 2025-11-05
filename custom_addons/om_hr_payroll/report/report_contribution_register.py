# -*- coding:utf-8 -*-
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ContributionRegisterReport(models.AbstractModel):
    _name = 'report.om_om_hr_payroll.report_contribution_register'
    _description = 'Payroll Contribution Register Report'

    def _get_payslip_lines(self, register_ids, date_from, date_to):
        """Return dict: { register_id: recordset(hr.payslip.line) }.

        Uses ORM search (safer than raw SQL), and uses overlap condition for payslip dates.
        """
        result = {}
        if not register_ids:
            _logger.debug("No register_ids provided to _get_payslip_lines")
            return result

        # normalize dates (strings -> date)
        if isinstance(date_from, str):
            date_from_parsed = fields.Date.from_string(date_from)
        else:
            date_from_parsed = date_from
        if isinstance(date_to, str):
            date_to_parsed = fields.Date.from_string(date_to)
        else:
            date_to_parsed = date_to

        # domain: payslip state done, lines with register in registers,
        # and payslip dates that overlap the provided range
        payslip_domain = [
            ('state', '=', 'done'),
            ('date_from', '<=', date_to_parsed),
            ('date_to', '>=', date_from_parsed),
        ]
        payslips = self.env['hr.payslip'].search(payslip_domain)
        if not payslips:
            _logger.debug("No payslips found in date range %s - %s", date_from_parsed, date_to_parsed)
            return result

        line_domain = [
            ('slip_id', 'in', payslips.ids),
            ('register_id', 'in', register_ids),
        ]
        lines = self.env['hr.payslip.line'].search(line_domain, order='slip_id, sequence')
        _logger.debug("Found %s payslip lines for registers %s", len(lines), register_ids)

        for reg_id in register_ids:
            reg_lines = lines.filtered(lambda l: l.register_id and l.register_id.id == int(reg_id))
            result[int(reg_id)] = reg_lines

        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data or not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        # docids should be the selected registers; fallback to context active_ids
        register_ids = docids or self.env.context.get('active_ids', [])
        _logger.debug("Report called for register_ids=%s docids=%s context.active_ids=%s", register_ids, docids,
                      self.env.context.get('active_ids'))

        contrib_registers = self.env['hr.contribution.register'].browse(register_ids)
        date_from = data['form'].get('date_from', fields.Date.today())
        date_to = data['form'].get('date_to', str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])

        lines_data = self._get_payslip_lines(register_ids, date_from, date_to)
        lines_total = {}
        for register in contrib_registers:
            lines = lines_data.get(register.id) or self.env['hr.payslip.line']
            lines_total[register.id] = float(sum(lines.mapped('total'))) if lines else 0.0

        return {
            'doc_ids': register_ids,
            'doc_model': 'hr.contribution.register',
            'docs': contrib_registers,
            'data': data,
            'lines_data': lines_data,
            'lines_total': lines_total
        }

# # -*- coding:utf-8 -*-
#
#
# from datetime import datetime
# from dateutil.relativedelta import relativedelta
#
# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
#
#
# class ContributionRegisterReport(models.AbstractModel):
#     _name = 'report.om_om_hr_payroll.report_contribution_register'
#     _description = 'Payroll Contribution Register Report'
#
#     def _get_payslip_lines(self, register_ids, date_from, date_to):
#         result = {}
#         self.env.cr.execute("""
#             SELECT pl.id from hr_payslip_line as pl
#             LEFT JOIN hr_payslip AS hp on (pl.slip_id = hp.id)
#             WHERE (hp.date_from >= %s) AND (hp.date_to <= %s)
#             AND pl.register_id in %s
#             AND hp.state = 'done'
#             ORDER BY pl.slip_id, pl.sequence""",
#             (date_from, date_to, tuple(register_ids)))
#         line_ids = [x[0] for x in self.env.cr.fetchall()]
#         for line in self.env['hr.payslip.line'].browse(line_ids):
#             result.setdefault(line.register_id.id, self.env['hr.payslip.line'])
#             result[line.register_id.id] += line
#         return result
#
#     @api.model
#     def _get_report_values(self, docids, data=None):
#         if not data.get('form'):
#             raise UserError(_("Form content is missing, this report cannot be printed."))
#
#         register_ids = self.env.context.get('active_ids', [])
#         contrib_registers = self.env['hr.contribution.register'].browse(register_ids)
#         date_from = data['form'].get('date_from', fields.Date.today())
#         date_to = data['form'].get('date_to', str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10])
#         lines_data = self._get_payslip_lines(register_ids, date_from, date_to)
#         lines_total = {}
#         for register in contrib_registers:
#             lines = lines_data.get(register.id)
#             lines_total[register.id] = lines and sum(lines.mapped('total')) or 0.0
#         return {
#             'doc_ids': register_ids,
#             'doc_model': 'hr.contribution.register',
#             'docs': contrib_registers,
#             'data': data,
#             'lines_data': lines_data,
#             'lines_total': lines_total
#         }
