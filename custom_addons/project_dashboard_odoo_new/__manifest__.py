{
    'name': 'Project Dashboard test',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': """Get a Detailed View for Project.""",
    'description': """In this dashboard user can get the Detailed Information 
     about Project, Task, Employee, Hours recorded, Total Margin and Total 
     Sale Orders.""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['sale_management', 'project', 'sale_timesheet'],
    'data': ['views/dashboard_views.xml',
             # 'views/project_project_views.xml'
             ],
    'assets': {
        'web.assets_backend': [
            'https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.js',
            'https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css',

            'project_dashboard_odoo_new/static/src/js/dashboard.js',
            'project_dashboard_odoo_new/static/src/css/dashboard.css',
            'project_dashboard_odoo_new/static/src/xml/dashboard_templates.xml',
            'project_dashboard_odoo_new/static/src/js/summary_dashboard.js',
            'project_dashboard_odoo_new/static/src/xml/summary_dashboard_templates.xml',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.4/Chart.js',
            'https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@0.7.0'
        ]},
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
