# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Data Recycle',
    'version': '1.3',
    'category': 'Productivity/Data Cleaning',
    'summary': 'Find old records and archive/delete them',
    'description': """Find old records and archive/delete them""",
    'depends': ['mail','base','project','sms'],
    'data': [
        'data/ir_cron_data.xml',
        'data/holiday_notification_cron.xml',
        'views/data_recycle_model_views.xml',
        'views/data_recycle_record_views.xml',
        'views/data_cleaning_menu.xml',
        'views/data_recycle_templates.xml',
        'views/data_recycle_error_wizard_views.xml',
        'security/ir.model.access.csv',
        'security/security_templates.xml',
        'views/views.xml',
        'views/configuration_manager_views.xml',
        'views/whatsapp_message_views.xml',
        'views/whatsapp_template_views.xml',
        'views/res_company_views.xml',
        'views/email_template.xml',
        'wizard/whatsapp_authenticate_views.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'data_recycle/static/src/views/*.js',
            'data_recycle/static/src/views/*.xml',
        ],
    },
    'license': 'LGPL-3',
}
