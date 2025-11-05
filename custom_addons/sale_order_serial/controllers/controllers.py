# -*- coding: utf-8 -*-
# from odoo import http


# class SaleOrderSerial(http.Controller):
#     @http.route('/sale_order_serial/sale_order_serial', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sale_order_serial/sale_order_serial/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sale_order_serial.listing', {
#             'root': '/sale_order_serial/sale_order_serial',
#             'objects': http.request.env['sale_order_serial.sale_order_serial'].search([]),
#         })

#     @http.route('/sale_order_serial/sale_order_serial/objects/<model("sale_order_serial.sale_order_serial"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sale_order_serial.object', {
#             'object': obj
#         })

