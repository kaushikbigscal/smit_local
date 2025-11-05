# -*- coding: utf-8 -*-
# from odoo import http


# class LeadDynamicForm(http.Controller):
#     @http.route('/lead_dynamic_form/lead_dynamic_form', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/lead_dynamic_form/lead_dynamic_form/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('lead_dynamic_form.listing', {
#             'root': '/lead_dynamic_form/lead_dynamic_form',
#             'objects': http.request.env['lead_dynamic_form.lead_dynamic_form'].search([]),
#         })

#     @http.route('/lead_dynamic_form/lead_dynamic_form/objects/<model("lead_dynamic_form.lead_dynamic_form"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('lead_dynamic_form.object', {
#             'object': obj
#         })

