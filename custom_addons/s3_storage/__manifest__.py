# -*- coding: utf-8 -*-
{
    'name': "Store Attachment on amazon S3",

    'summary': """Amazon Connector, Amazon Storage Connector, S3 Connector, S3 Attachment, Attachment Connector, Amazon S3 Storage, Cloud Connector, Amazon Cloud""",

    'description': """
        
    """,
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Extra Tools',
    'version': '17.0.1.1.8',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],
    #'uninstall_hook': 'uninstall_hook',
    # always loaded
    'data': [
        'data/ir_config_parameter.xml',
        'views/res_config_settings.xml',
        'data/ir_cron.xml',
        'views/ir_attachment.xml',
        'views/action.xml'

    ],
    
    'external_dependencies' : {
        'python' : ['boto3'],
    },
    'odoo-apps' : True,
}