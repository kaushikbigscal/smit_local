

{
    "name": "Project timesheet time control",
    "version": "17.0.1.0.1",
    "category": "Project",
    "author": "Tecnativa," "Odoo Community Association (OCA)",
    "maintainers": ["ernestotejeda"],
    "website": "https://github.com/OCA/project",
    "depends": [
        "hr_timesheet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_analytic_line_view.xml",
        "views/project_project_view.xml",
        "views/project_task_view.xml",
        "wizards/hr_timesheet_switch_view.xml",
    ],
    'assets': {
        'web.assets_backend': [
            '/project_timesheet_time_control/static/src/js/timesheet_geolocation.js',
        ],
    },
    "license": "AGPL-3",
    "installable": True,
    "post_init_hook": "post_init_hook",
}
