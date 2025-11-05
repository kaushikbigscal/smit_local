from odoo import http
from odoo.http import request

class EmployeeCertificationController(http.Controller):

    @http.route('/my/employee/certification', type='http', auth='user', website=True)
    def employee_certification(self, **kwargs):
        # Your logic to fetch data or render a template


        certifications = request.env['employee.certification'].search([])
        return request.render('employee_certification.certification_templates', {
            'certifications': certifications,

        })
