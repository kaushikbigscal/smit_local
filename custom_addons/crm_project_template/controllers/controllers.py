# -*- coding: utf-8 -*-
# from odoo import http


# class CrmProjectTemplate(http.Controller):
#     @http.route('/crm_project_template/crm_project_template', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/crm_project_template/crm_project_template/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('crm_project_template.listing', {
#             'root': '/crm_project_template/crm_project_template',
#             'objects': http.request.env['crm_project_template.crm_project_template'].search([]),
#         })

#     @http.route('/crm_project_template/crm_project_template/objects/<model("crm_project_template.crm_project_template"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('crm_project_template.object', {
#             'object': obj
#         })

