{
    'name': 'HR Attendance Address',
    'version': '1.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Add address to attendance check-ins',
    'description': """
This module adds the ability to show the address of the location where an employee checked in.
    """,
    'depends': ['hr_attendance'],
    'data': [
    'views/hr_attendance_views.xml',
],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}