# -*- coding: utf-8 -*-
# from odoo import http


# class Firebase(http.Controller):
#     @http.route('/firebase/firebase', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/firebase/firebase/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('firebase.listing', {
#             'root': '/firebase/firebase',
#             'objects': http.request.env['firebase.firebase'].search([]),
#         })

#     @http.route('/firebase/firebase/objects/<model("firebase.firebase"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('firebase.object', {
#             'object': obj
#         })

