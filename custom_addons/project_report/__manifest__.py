{
    'name': 'Project Report',
    'version': '1.0',
    'depends': ['base','project', 'hr_timesheet'],
    'author': 'Dhruti',
    'category': 'Project',
    'summary': 'Custom report showing timesheet per project/task',
    'data': [
        'views/views.xml',
        'views/project_report_wizard_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
}