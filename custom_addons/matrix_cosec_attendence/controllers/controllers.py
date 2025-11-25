# -*- coding: utf-8 -*-
# from odoo import http


# class MatrixCosecAttendence(http.Controller):
#     @http.route('/matrix_cosec_attendence/matrix_cosec_attendence', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/matrix_cosec_attendence/matrix_cosec_attendence/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('matrix_cosec_attendence.listing', {
#             'root': '/matrix_cosec_attendence/matrix_cosec_attendence',
#             'objects': http.request.env['matrix_cosec_attendence.matrix_cosec_attendence'].search([]),
#         })

#     @http.route('/matrix_cosec_attendence/matrix_cosec_attendence/objects/<model("matrix_cosec_attendence.matrix_cosec_attendence"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('matrix_cosec_attendence.object', {
#             'object': obj
#         })

