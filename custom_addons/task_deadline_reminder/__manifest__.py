{
    'name': 'Web Reminders',
    'version': '1.0',
    'summary': 'Send and Store Task Deadline Reminders',
    'author': 'Your Name',
    'depends': ['project', 'mail', 'bus','hr', 'resource'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings.xml',
        'views/mail_activity_schedule_inherit.xml',
        'views/project_task_views.xml',
        'views/reminder_task_queue_views.xml',
        'views/res_company_views.xml',
        'views/res_user_views.xml',
        'views/reminder_types_views.xml',
        'data/task_deadline_reminder_cron.xml',
        'data/attendance_reminder.xml',
        'data/auto_day_out_cron.xml',
        'data/overdue_task_reminder_cron.xml',
        'data/amc_contract_cron.xml',
    ],
    'installable': True,
    'application': True,
    'post_init_hook': '',
    'assets': {
        'web.assets_backend': [
            'task_deadline_reminder/static/src/js/notification_bell_icon.js',
            'task_deadline_reminder/static/src/xml/notification_bell_icon.xml',
            'task_deadline_reminder/static/src/css/reminder_styles.css',
            'task_deadline_reminder/static/src/css/inline_time_deadline.css',
        ],
        'web.assets_frontend': [

        ],
        'web.qunit_suite_tests': [

        ],
        'web.assets_tests': [

        ],
    },
}
