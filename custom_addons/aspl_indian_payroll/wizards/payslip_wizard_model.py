# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
from datetime import date

from openpyxl import Workbook

from odoo import fields, models


class PayslipWizards(models.TransientModel):
    _name = 'payslip.file.wizard'
    _description = "Generate Payslip Excel File"

    bank_selection = fields.Many2one('res.partner.bank', string='Select Bank', required=True)
    payment_date = fields.Date(string='Payment Date', required=True, default=date.today())

    def _get_template(self):
        self.banksheet_template = base64.b64encode(open("/tmp/bank_sheet.xlsx", "rb").read())

    banksheet_template = fields.Binary('Template', compute="_get_template", default=date.today())

    def get_contract_template(self):
        return {
            'type': 'ir.actions.act_url',
            'name': 'contract',
            'url': '/web/content/payslip.file.wizard/%s/banksheet_template/bank_sheet.xlsx?download=true' % (self.id),
        }

    def generate_excel(self, **post):
        wb = Workbook()
        ws = wb.active
        ws.append(["PYMT_PROD_TYPE_CODE", "PYMT_MODE", "DEBIT_ACC_NO", "BNF_NAME", "BENE_ACC_NO", "BENE_IFSC", "AMOUNT",
                   "DEBIT_NARR", "CREDIT_NARR", "MOBILE_NUM", "EMAIL_ID", "REMARK", "PYMT_DATE", "REF_NO", "ADDL_INFO1",
                   "ADDL_INFO2", "ADDL_INFO3", "ADDL_INFO4", "ADDL_INFO5", "LEI_NUMBER"])
        name = "/tmp/bank_sheet.xlsx"
        wb.save(name)
        batch_id = self.env.context['batch_id']
        payslip_batch_details = self.env['hr.payslip.run'].search([('id', '=', batch_id)])
        net_amount = 0
        for data in payslip_batch_details.slip_ids:
            if data.is_blocked:
                continue
            for info in data.line_ids:
                if info.code == 'NET':
                    net_amount = info.amount
                if info.code == 'NCC':
                    net_amount = info.amount

            list = ['PAB_VENDOR', 'NEFT', self.bank_selection.bank_id.name, data.employee_id.name,
                    data.employee_id.bank_account_no, data.employee_id.bank_id.bic, net_amount, '', '', '', '', '',
                    self.payment_date]

            ws.append(list)
            wb.save(name)

        return self.get_contract_template()
