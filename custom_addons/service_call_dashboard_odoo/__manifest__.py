{
    'name': 'Service Call Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'sequece': 1,
    'summary': """Get a Detailed View for Project.""",
    'description': """In this dashboard user can get the Detailed Information 
     about Calls, Customers, Employee, Hours recorded, Total Margin and Total 
     Sale Orders.""",
    # 'depends': ['sale_management', 'project', 'sale_timesheet'],

    'depends': [
        'sale_management',
        'project',
        'sale_timesheet',
        'web',
    ],
    'data': ['views/dashboard_views.xml'],
    'assets': {
        'web.assets_backend': [
            'service_call_dashboard_odoo/static/src/xml/dashboard_templates.xml',
            'service_call_dashboard_odoo/static/src/js/dashboard.js',
            'service_call_dashboard_odoo/static/src/css/dashboard.css',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.4/Chart.js',
            'web/static/src/views/form/**/*',

        ]},
    # 'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}


