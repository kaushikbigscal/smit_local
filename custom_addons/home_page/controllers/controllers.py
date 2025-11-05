# -*- coding: utf-8 -*-
# from odoo import http


# class HomePage(http.Controller):
#     @http.route('/home_page/home_page', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/home_page/home_page/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('home_page.listing', {
#             'root': '/home_page/home_page',
#             'objects': http.request.env['home_page.home_page'].search([]),
#         })

#     @http.route('/home_page/home_page/objects/<model("home_page.home_page"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('home_page.object', {
#             'object': obj
#         })

