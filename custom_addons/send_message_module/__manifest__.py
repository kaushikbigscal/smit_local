# -*- coding: utf-8 -*-
{
    'name': 'send_message_module',
    'version': '2.0.0',
    'summary': 'send_message_module',
    'sequence': -100,
    'description': """send_message_module""",
    'category': 'send message',
    'author': 'satyam',
    'maintainer': 'satyam',
    # 'website': 'https://www.odoomates.tech',
    'license': 'AGPL-3',
    'depends': [ 'base','mail',],
    'data': [
        'security/ir.model.access.csv',
        'views/mail_message.xml',
        'views/token_view.xml'
    ],
    'demo': [],
    # 'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
}