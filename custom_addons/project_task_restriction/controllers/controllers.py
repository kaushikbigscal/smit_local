# -*- coding: utf-8 -*-
# from odoo import http


# class ProjectTaskRestriction(http.Controller):
#     @http.route('/project_task_restriction/project_task_restriction', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project_task_restriction/project_task_restriction/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('project_task_restriction.listing', {
#             'root': '/project_task_restriction/project_task_restriction',
#             'objects': http.request.env['project_task_restriction.project_task_restriction'].search([]),
#         })

#     @http.route('/project_task_restriction/project_task_restriction/objects/<model("project_task_restriction.project_task_restriction"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project_task_restriction.object', {
#             'object': obj
#         })

