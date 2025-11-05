# -*- coding: utf-8 -*-
# from odoo import http


# class HalfDayLeave(http.Controller):
#     @http.route('/half_day_leave/half_day_leave', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/half_day_leave/half_day_leave/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('half_day_leave.listing', {
#             'root': '/half_day_leave/half_day_leave',
#             'objects': http.request.env['half_day_leave.half_day_leave'].search([]),
#         })

#     @http.route('/half_day_leave/half_day_leave/objects/<model("half_day_leave.half_day_leave"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('half_day_leave.object', {
#             'object': obj
#         })

