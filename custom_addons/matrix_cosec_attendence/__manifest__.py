{
    'name': 'Matrix Attendance Sync',
    'version': '1.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Sync attendance from Matrix biometric system',
    'description': """
        This module synchronizes attendance records from Matrix biometric system to Odoo attendance.
        Features:
        - Daily automatic sync of attendance records
        - Configuration for API credentials
        - Mapping of biometric IDs to employees
    """,
    'depends': ['base', 'hr', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/matrix_config_views.xml',
        'views/matrix_attendance_log_views.xml',
        'data/cronjob.xml',
	'views/matrix_server_error_log.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}