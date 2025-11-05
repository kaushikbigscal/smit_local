{
    'name': 'Advanced Attendance Control',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Control multiple check-ins/outs for employees',
    'description': """
        This module adds a global setting to allow or disallow multiple check-ins/outs for employees.
    """,
    'depends': ['hr_attendance', 'hr_holidays', 'project', 'base'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        # 'views/templates.xml',

    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/custom_attendance/static/src/js/button_in_tree.js',
    #         '/custom_attendance/static/src/xml/button_in_tree.xml',
    #     ],
    # },

    'installable': True,
    'auto_install': False,

}
