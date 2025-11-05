# -*- coding: utf-8 -*-
{
    'name': "Dynamic Form Configuration",

    'summary': "Dynamic Form Configuration For Mobile",

    'description': """
Dynamic Form Configuration For Mobile
    """,

    'author': "Effezient Pvt Ltd.",

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'Settings',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/dynamic_form_configuration/static/src/js/button_in_tree.js',
            '/dynamic_form_configuration/static/src/xml/button_in_tree.xml',
        ],
    },

    'installable': True,
    'auto_install': False,
}
