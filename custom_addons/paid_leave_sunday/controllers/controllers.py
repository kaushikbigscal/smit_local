# -*- coding: utf-8 -*-
# from odoo import http


# class PaidLaveSunday(http.Controller):
#     @http.route('/paid_lave_sunday/paid_lave_sunday', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/paid_lave_sunday/paid_lave_sunday/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('paid_lave_sunday.listing', {
#             'root': '/paid_lave_sunday/paid_lave_sunday',
#             'objects': http.request.env['paid_lave_sunday.paid_lave_sunday'].search([]),
#         })

#     @http.route('/paid_lave_sunday/paid_lave_sunday/objects/<model("paid_lave_sunday.paid_lave_sunday"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('paid_lave_sunday.object', {
#             'object': obj
#         })

