# -*- coding: utf-8 -*-
# from odoo import http


# class ProjectReport(http.Controller):
#     @http.route('/project_report/project_report', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project_report/project_report/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('project_report.listing', {
#             'root': '/project_report/project_report',
#             'objects': http.request.env['project_report.project_report'].search([]),
#         })

#     @http.route('/project_report/project_report/objects/<model("project_report.project_report"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project_report.object', {
#             'object': obj
#         })

