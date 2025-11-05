# -*- coding: utf-8 -*-
{
    'name': "Lead Dynamic Form",
    'summary': "Short (1 phrase/line) summary of the module's purpose",
    'description': """
Long description of module's purpose
    """,
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'crm'],

    'data': [
        'security/ir.model.access.csv',
        'data/lead_type_data.xml',
        'views/lead_type_master.xml',
        'views/crm_lead_inherit.xml',
        'views/store_code_master.xml',
    ],

}

