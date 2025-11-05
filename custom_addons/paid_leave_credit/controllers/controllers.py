# -*- coding: utf-8 -*-
# from odoo import http


# class PaidLeaveCredit(http.Controller):
#     @http.route('/paid_leave_credit/paid_leave_credit', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/paid_leave_credit/paid_leave_credit/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('paid_leave_credit.listing', {
#             'root': '/paid_leave_credit/paid_leave_credit',
#             'objects': http.request.env['paid_leave_credit.paid_leave_credit'].search([]),
#         })

#     @http.route('/paid_leave_credit/paid_leave_credit/objects/<model("paid_leave_credit.paid_leave_credit"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('paid_leave_credit.object', {
#             'object': obj
#         })

