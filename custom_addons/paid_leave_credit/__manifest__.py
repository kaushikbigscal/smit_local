# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Paid Leave Credit',
    'version': '1.0',
    'category': 'Human Resources',
    'author': 'smit',
    'website': 'https://www.yourcompany.com',
    'depends': ['hr_holidays'],
    'version': '0.1',

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/paid_leave_action.xml',
        'views/paid_leave_config_views.xml',
    ],
    'installable': True,
    'application': False,


}
