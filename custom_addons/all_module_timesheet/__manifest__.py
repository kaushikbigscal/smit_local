# -*- coding: utf-8 -*-
{
    'name': "all_module_timesheet",

    'summary': "Updated timesheet Module.",

    'description': """
Long description of module's purpose
    """,

    'author': "Effezient",

    # for the full list
    'category': 'Timesheet',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr_timesheet', 'web', 'sale_timesheet'],

    # always loaded
    'data': [
        'data/timesheet_category_data.xml',
        'security/dar_record_rules.xml',
        'security/ir.model.access.csv',
        'views/timesheet_category_views.xml',
        'views/account_analytic_line_views.xml',
        'views/project_task_views.xml',
        # 'views/crm_lead_views.xml',
        'views/res_config_settings_views.xml',
        'report/daily_activity_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'all_module_timesheet/static/src/js/geolocation_timer_patch.js',
        ],
    }

}
