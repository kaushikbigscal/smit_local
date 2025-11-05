# -*- coding: utf-8 -*-
{
    'name': "sequence_reset",

    'summary': "Reset the auto generated sequance",

    'description': """
Reset the auto generated sequance based on selection of monthly or yearly. 
    """,

    'author': "Effezient",
    'website': "https://www.effezient.com",

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'Technical',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        # 'views/project_task.xml',
    ],
'installable': True,
    'application': True,

}

