{
    'name': "Service Call",
    'summary': "Schedule and track onsite operations, time and material",
    'description': """
Service Call
=========================
This module adds the features needed for a modern Services Call management.
It installs the following apps:
- Project
- Timesheet

Adds the following options:
- reports on tasks
- Services Call app with custom view for onsite worker
- add products on tasks

    """,
    'author': 'Effezient',
    'license': 'LGPL-3',
    'category': 'Services/Service Call',
    'sequence': 170,
    'version': '1.0',
    'depends': ['project', 'all_module_timesheet', 'base_geolocalize', 'base', 'sale'],
    'data': [
        'data/mail_template_data.xml',
        'security/fsm_security.xml',
        'security/send_whatsapp_groups.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/hr_timesheet_views.xml',
        'views/fsm_views.xml',
        'views/project_task_views.xml',
        'report/project_report_views.xml',
        'views/res_partner_views.xml',
        'views/project_sharing_views.xml',
        'views/project_portal_templates.xml',
        'views/complaint_type_views.xml',
        'views/service_type_views.xml',
	'views/service_charge_type_views.xml',
        'data/fsm_stage.xml',
        'data/unique_number.xml',
        'data/call_type_data.xml',
        'views/pending_reason_view.xml',
        'views/service_center.xml',
        'views/res_company_views.xml',
        'wizard/service_charge_wizard_views.xml',
        'views/customer_product_maping_views.xml',
        'views/configuration_manager_views.xml',
        'views/whatsapp_message_views.xml',
        'views/whatsapp_template_views.xml',
        'wizard/whatsapp_authenticate_views.xml',
        'views/actual_reason.xml',
        'views/item_receipt_field_views.xml',
        'views/call_typewise_summary_report.xml',
        'views/service_charge_report_views.xml',
        'views/supervisor_visibility_views.xml',
        'views/feedback.xml',

    ],
    'application': True,
    'post_init_hook': 'create_field_service_project',
    'assets': {
        'web.assets_backend': [
            'industry_fsm/static/src/**/*',
            'industry_fsm/static/src/js/month_field.js',
            'industry_fsm/static/src/js/no_open_form.js',
            'industry_fsm/static/src/js/button_refresh_fields.js',
            'industry_fsm/static/src/xml/button_refresh_fields.xml',
            'industry_fsm/static/src/js/chatter_activity/chatter_patch.js',
            'industry_fsm/static/src/js/chatter_activity/download_chat.xml',
            'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
            'industry_fsm/static/src/js/add_server_action/restric_form_view.js',
            'industry_fsm/static/src/js/fsm_calendar_renderer.js',
            "industry_fsm/static/src/js/toggle_more_options.js",
            'industry_fsm/static/src/js/fsm_project_task_calendar_controller.js',
            'industry_fsm/static/src/js/fsm_project_task_calendar_view.js',
            'industry_fsm/static/src/css/fsm_styles.css',
 
        ],
        'web.assets_frontend': [
            'industry_fsm/static/src/js/tours/**/*',
        ],
        'web.qunit_suite_tests': [
            'industry_fsm/static/tests/**/*.js',
        ],
        'web.assets_tests': [
            'industry_fsm/static/tests/tours/**/*',
        ],
    },
}
