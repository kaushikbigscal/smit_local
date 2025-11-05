{
    'name': 'Device Security Lock',
    'version': '17.0.1.0.0',
    'category': 'Security',
    'summary': 'Device-based login restrictions for enhanced security',
    'description': '''
        Device Security Lock Module
        ===========================

        This module provides device-based login restrictions to enhance security:

        Features:
        ---------
        * Company-level device lock enable/disable
        * User-level login restrictions (Web, Mobile)
        * Device UUID tracking and validation
        * Admin reset functionality for device locks
        * Support team troubleshooting capabilities

        How it works:
        -------------
        1. Admin enables device lock at company level
        2. Users are restricted based on their login restriction settings
        3. On first login, device UUID is stored
        4. Subsequent logins are validated against stored UUID
        5. Admin can reset device locks when users change devices

        Perfect for organizations requiring strict device control!
    ''',
    'author': 'Effezient',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/user_device_lock_views.xml',
        'views/res_company_views.xml',
        'views/res_users_view.xml',
        'views/login_view_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'device_security/static/src/js/device.js',
            'device_security/static/src/js/copy_button.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
