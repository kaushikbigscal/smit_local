{
    'name': 'Web Auto Refresh',
    'version': '1.1',
    'summary': 'Automatically refresh web pages after a configured time interval',
    'author': 'Smit',
    'depends': ['base', 'web'],
    'data': [
        'views/res_config_settings_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'web_auto_refresh/static/src/js/auto_refresh.js',
        ],
        'web.assets_frontend': [
            'web_auto_refresh/static/src/js/auto_refresh.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
}
