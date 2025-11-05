# -*- coding: utf-8 -*-
{
    'name': "home_page",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','calendar','crm','project'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/calendar_view.xml',
        'views/calendar_rule_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'home_page/static/src/views/calendar_dashboard.xml',
            'home_page/static/src/views/calendar_rules.xml',
            'home_page/static/src/views/calendar_view.xml',

            'home_page/static/src/views/calendar_dashboard.js',
            'home_page/static/src/views/calendar_rules.js',
            'home_page/static/src/views/calendar_view.js',
        ],
    },
}

