{
    'name': 'Firebase Cloud Messaging Notifications',
    'version': '1.0',
    'category': 'Communication',
    'summary': 'Implement Firebase Cloud Messaging for mobile push notifications',
    'description': """
    Provides Firebase Cloud Messaging (FCM) integration for Odoo mobile notifications.
    - Device token management
    - Push notification sending
    - Support for various Odoo models
    """,
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': [
        'base', 
        'mail', 
        'project'  # Optional, remove if not using project notifications
    ],
    'external_dependencies': {
        'python': ['firebase_admin']
    },
    'data': [
        'security/ir.model.access.csv',
        'views/mobile_device_token_views.xml',
        'views/notification_log_views.xml',
        'data/notification_config.xml',
        'wizards/fcm_test_notification_wizard_view.xml',
        'views/attendance_notification_view.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}