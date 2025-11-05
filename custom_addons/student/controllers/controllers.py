from odoo import http
from odoo.http import request

class StudentListController(http.Controller):

    @http.route('/my/student/list', type='http', auth='user', website=True)

    def student_list(self,**kwargs):

        students = request.env['wb.student'].search([])
        return request.render('student.student_list_templates',
                              {'students': students,
                               })

# class mycontroller(http.Controller):
#     @http.route('/my/api_controller',type='http', auth='user', website=True)
#
#     def demo(self):
#         return http.Response("hello this is api..")