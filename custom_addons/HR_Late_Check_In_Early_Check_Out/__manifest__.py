{
    'name': 'HR Late Check-In Early Check-Out',
    'version': '1.0',
    'summary': 'Apply half-day leave for late check-ins',
    'category': 'Human Resources',
    'author': 'Your Name',
    'depends': ['hr', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/hr_employee.xml',
        'views/res_config_settings_view.xml'
    ],
    'installable': True,
    'application': False,
}
