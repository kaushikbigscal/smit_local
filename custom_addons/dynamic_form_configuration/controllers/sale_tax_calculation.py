from odoo import http
from odoo.http import request


# class SaleOrderLineAPI(http.Controller):
#
#     @http.route('/web/sale/compute_line_totals', type='json', auth='user')
#     def compute_line_totals(self, **kwargs):
#         product_id = kwargs.get('product_id')
#         qty = kwargs.get('product_uom_qty')
#         price_unit = kwargs.get('price_unit')
#         tax_ids = kwargs.get('tax_id', [])
#
#         if not all([product_id, qty, price_unit]):
#             return {'error': 'Missing required fields'}
#
#         env = request.env
#         product = env['product.product'].browse(product_id)
#
#         if not product.exists():
#             return {'error': 'Invalid product_id'}
#
#         # Dummy order for tax context
#         dummy_order = env['sale.order'].new({
#             'partner_id': env.user.partner_id.id,
#             'company_id': env.user.company_id.id,
#             'currency_id': env.user.company_id.currency_id.id,
#         })
#
#         # Virtual sale order line
#         line = env['sale.order.line'].new({
#             'order_id': dummy_order,
#             'product_id': product.id,
#             'product_uom_qty': qty,
#             'price_unit': price_unit,
#             'tax_id': [(6, 0, tax_ids)],
#             'product_uom': product.uom_id.id,
#             'company_id': env.user.company_id.id,
#             'currency_id': env.user.company_id.currency_id.id,
#         })
#
#         line._compute_amount()
#
#         return {
#             'price_subtotal': line.price_subtotal,
#             'price_tax': line.price_tax,
#             'price_total': line.price_total,
#         }
#
#
# class SaleOrderTaxAPI(http.Controller):
#
#     @http.route('/web/sale/final_totals', type='json', auth='user')
#     def sale_tax_totals(self, **post):
#         order_lines_data = post.get('order_line')
#         partner_id = post.get('partner_id')
#
#         if not order_lines_data or not partner_id:
#             return {"error": "Missing required 'order_line' or 'partner_id'"}
#
#         env = request.env
#         partner = env['res.partner'].browse(partner_id)
#
#         order_lines_values = []
#         for line_data in order_lines_data:
#             product = env['product.product'].browse(line_data['product_id'])  # <-- Use product_id
#
#             if not product.exists():
#                 continue
#
#             order_lines_values.append((0, 0, {
#                 'product_id': product.id,
#                 'product_uom_qty': line_data.get('product_uom_qty', 1),
#                 'price_unit': line_data.get('price_unit', 0.0),
#                 'tax_id': [(6, 0, line_data.get('tax_id', []))],
#                 'product_uom': product.uom_id.id,
#                 'name': product.name or '',
#             }))
#
#         order = env['sale.order'].new({
#             'partner_id': partner.id,
#             'order_line': order_lines_values,
#             'company_id': env.company.id,
#             'currency_id': env.company.currency_id.id,
#         })
#
#         order._compute_tax_totals()
#
#         return {
#             "tax_totals": order.tax_totals,
#         }

class SaleOrderLineAPI(http.Controller):

    @http.route('/web/sale/compute_line_totals', type='json', auth='user')
    def compute_line_totals(self, **kwargs):
        product_id = kwargs.get('product_id')
        qty = kwargs.get('product_uom_qty')
        price_unit = kwargs.get('price_unit')
        tax_ids = kwargs.get('tax_id', [])
        discount = kwargs.get('discount', 0.0)  # Add this line

        if not all([product_id, qty, price_unit]):
            return {'error': 'Missing required fields'}

        env = request.env
        product = env['product.product'].browse(product_id)

        if not product.exists():
            return {'error': 'Invalid product_id'}

        # Dummy order for tax context
        dummy_order = env['sale.order'].new({
            'partner_id': env.user.partner_id.id,
            'company_id': env.user.company_id.id,
            'currency_id': env.user.company_id.currency_id.id,
        })

        # Virtual sale order line
        line = env['sale.order.line'].new({
            'order_id': dummy_order,
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': price_unit,
            'discount': discount,  # Include discount here
            'tax_id': [(6, 0, tax_ids)],
            'product_uom': product.uom_id.id,
            'company_id': env.user.company_id.id,
            'currency_id': env.user.company_id.currency_id.id,
        })

        line._compute_amount()

        return {
            'price_subtotal': line.price_subtotal,
            'price_tax': line.price_tax,
            'price_total': line.price_total,
        }


class SaleOrderTaxAPI(http.Controller):

    @http.route('/web/sale/final_totals', type='json', auth='user')
    def sale_tax_totals(self, **post):
        order_lines_data = post.get('order_line')
        partner_id = post.get('partner_id')

        if not order_lines_data or not partner_id:
            return {"error": "Missing required 'order_line' or 'partner_id'"}

        env = request.env
        partner = env['res.partner'].browse(partner_id)

        order_lines_values = []
        for line_data in order_lines_data:
            product = env['product.product'].browse(line_data['product_id'])

            if not product.exists():
                continue

            order_lines_values.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': line_data.get('product_uom_qty', 1),
                'price_unit': line_data.get('price_unit', 0.0),
                'discount': line_data.get('discount', 0.0),  # Include discount
                'tax_id': [(6, 0, line_data.get('tax_id', []))],
                'product_uom': product.uom_id.id,
                'name': product.name or '',
            }))

        order = env['sale.order'].new({
            'partner_id': partner.id,
            'order_line': order_lines_values,
            'company_id': env.company.id,
            'currency_id': env.company.currency_id.id,
        })

        order._compute_tax_totals()

        return {
            "tax_totals": order.tax_totals,
        }
