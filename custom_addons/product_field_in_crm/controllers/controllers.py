# -*- coding: utf-8 -*-
# from odoo import http


# class TaskStageRestriction(http.Controller):
#     @http.route('/task_stage_restriction/task_stage_restriction', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/task_stage_restriction/task_stage_restriction/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('task_stage_restriction.listing', {
#             'root': '/task_stage_restriction/task_stage_restriction',
#             'objects': http.request.env['task_stage_restriction.task_stage_restriction'].search([]),
#         })

#     @http.route('/task_stage_restriction/task_stage_restriction/objects/<model("task_stage_restriction.task_stage_restriction"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('task_stage_restriction.object', {
#             'object': obj
#         })

