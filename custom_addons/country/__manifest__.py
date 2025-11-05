{
    'name': 'Country State Management',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'Manage Countries and States',
    'sequence': 10,
    'description': """This module allows you to manage countries and their states.""",
    'author': 'Your Name',
    'website': 'https://www.yourwebsite.com',
    'depends': ['base'],
    'data': [
        'views/country_state_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}