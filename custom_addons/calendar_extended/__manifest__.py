# -*- coding: utf-8 -*-
{
    'name': "calendar_extended",

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
    'depends': ['base','calendar','project','crm', 'all_module_timesheet','field_visit','web_map'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/quick_model_form_view.xml',
        'views/nearest_customer_map_view.xml',
    ],
    'assets': {
            'web.assets_backend': [
                'calendar/static/src/**/*',
            ],
        },
    }

