{
    'name': 'PWA',
    'version': '17.0.1.0.0',
    'summary': 'Hide HTML field toolbar on mobile until focused',
    'description': """
This module modifies the behavior of all HTML fields so that on mobile devices, 
the Summernote toolbar is hidden until the field is focused, similar to desktop behavior.
    """,
    'category': 'Web',
    'author': 'Your Name',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'pwa/static/src/js/html_field_patch.js',
            # 'pwa/static/src/css/tree_view.css',
            'pwa/static/src/css/sale_team_dashboard.css',
            'pwa/static/src/css/ios_dropdown_action.scss',
            'pwa/static/src/css/tax_totals_right.css',
            'pwa/static/src/css/custom_leave.css',

        ],
    },
    'installable': True,
    'application': False,
}