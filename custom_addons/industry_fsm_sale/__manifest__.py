# -*- coding: utf-8 -*-

{
    'name': "Service Call - Sale",
    'summary': "Schedule and track onsite operations, invoice time and material",
    'description': """
Create Sales order with timesheets and products from tasks
    """,
    'category': 'Services/Service Call',
    'version': '1.0',
    'depends': ['industry_fsm', 'sale_timesheet','stock'],
    'data': [
        'security/customer_product_groups.xml',
        'security/ir.model.access.csv',
        'data/auto_create_service_call_task.xml',
        'views/project_task_views.xml',
        'views/product_product_views.xml',
        'views/project_project_views.xml',
        'views/sale_order_views.xml',
        "views/project_sharing_views.xml",
        'views/project_portal_templates.xml',
        'report/custom_fields_service_report.xml',
        'data/mail_template_send_fsm_report.xml',
        'views/product_template_view.xml',
        'views/sale_order_line_view.xml',
        'views/sale_invoice_view.xml',
        'views/product_parts.xml',
        'report/report_item_receipt_template.xml',
	    'views/custom_calendar_view.xml',
        'views/service_call_count_report_views.xml',

    ],
    # 'auto_install': True,
    'author': 'smit',
    'post_init_hook': 'post_init',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_backend': [
            'industry_fsm_sale/static/src/components/**/*',
            'industry_fsm_sale/static/src/js/tours/**/*',
            'industry_fsm_sale/static/src/js/call_button.js',
            'industry_fsm_sale/static/src/xml/call_button_template.xml',
            # 'industry_fsm_sale/static/src/js/m2o_customer_product.js',
        ],
        'web.assets_tests': [
            'industry_fsm_sale/static/tests/tours/**/*',
        ],
        'web.assets_frontend': [
            'industry_fsm_sale/static/src/js/tours/**/*',
        ],
        'web.qunit_suite_tests': [
            'industry_fsm_sale/static/tests/**/*',
        ],
    },
    'license': 'LGPL-3',
}
