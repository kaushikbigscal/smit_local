from odoo import models, api
from datetime import datetime, timedelta


class PosOrder(models.Model):
    _inherit = 'pos.order'  # Inherit the pos.order model instead of creating a new one

    @api.model
    def get_today_total_sales(self):
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        domain = [
            ('state', '=', 'invoiced'),
            ('date_order', '>=', today_start),
            ('date_order', '<', today_end),
            ('company_id', '=', self.env.company.id)
        ]

        total_sales = sum(order.amount_total for order in self.search(domain))

        # Format the total with currency symbol
        currency_id = self.env.company.currency_id
        formatted_total = currency_id.symbol + ' ' + '{:,.2f}'.format(total_sales)

        return {
            'total': total_sales,
            'formatted_total': formatted_total
        }