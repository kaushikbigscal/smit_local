from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError

class AmcContractRenewWizard(models.TransientModel):
    _name = 'amc.contract.renew.wizard'
    _description = 'Replicate & Renew AMC Contract'

    contract_id = fields.Many2one('amc.contract', string="Original Contract", required=True, readonly=True)
    name = fields.Char(string='New Contract Name', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    technician_ids = fields.Many2many('res.users', string='Technicians')


    @api.model
    def default_get(self, fields):
        res = super(AmcContractRenewWizard, self).default_get(fields)
        # Set the default start_date as the next day after the original contract's end_date
        if 'contract_id' in res and res['contract_id']:
            contract = self.env['amc.contract'].browse(res['contract_id'])
            if contract.end_date:
                res['start_date'] = contract.end_date + timedelta(days=1)
                res['end_date'] = res['start_date'] + timedelta(days=364)  # 1-year contract
        return res

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date:
            self.end_date = self.start_date + timedelta(days=364)  # 1-year contract

    def action_renew_contract(self):
        self.ensure_one()
        original_contract_name = self.contract_id.name
        if self.start_date <= self.contract_id.end_date:
            raise UserError(
                f"The start date must be later than the end date of the {original_contract_name} contract.")

        # Step 1: Create new base contract
        new_contract = self.contract_id.copy({
            'name': self.name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'user_ids': [(6, 0, self.technician_ids.ids)],
            'stage_id': 'draft',
            'total_amount': 0.0,
            'previous_contract_id': self.contract_id.id,
        })

        # Step 2: Copy Asset Lines
        for line in self.contract_id.asset_line_ids:
            line.copy({'contract_id': new_contract.id})

        # # Step 3: Copy Customer Product Lines
        # for line in self.contract_id.customer_product_ids:
        #     line.copy({'contract_id': new_contract.id})

        # Step 4: Redirect to new contract
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'amc.contract',
            'res_id': new_contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
