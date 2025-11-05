# -*- coding: utf-8 -*-
{
    'name': "paid_lave_sunday",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends':  ['base','hr','hr_attendance','hr_holidays','hr_timesheet','hr_timesheet_attendance','om_hr_payroll','aspl_indian_payroll'
    ],

    # always loaded
    'data': [
        'views/views.xml',
        'views/sunday_log_view.xml'
    ],
    # only loaded in demonstration mode

}

