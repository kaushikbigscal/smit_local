# -*- coding: utf-8 -*-
{
    'name': "hr_crm_timesheet",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Timesheet tracking for CRM module.
    """,

    'author': "Effezient",
    'website': "https://effezient.com/",

    # Categories can be used to filter modules in modules listing
    'category': 'Timesheets',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'all_module_timesheet', 'crm'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
    ],

}

