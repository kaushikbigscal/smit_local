# -*- coding: utf-8 -*-
# from odoo import http


# class TaskEvent(http.Controller):
#     @http.route('/task_event/task_event', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/task_event/task_event/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('task_event.listing', {
#             'root': '/task_event/task_event',
#             'objects': http.request.env['task_event.task_event'].search([]),
#         })

#     @http.route('/task_event/task_event/objects/<model("task_event.task_event"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('task_event.object', {
#             'object': obj
#         })

