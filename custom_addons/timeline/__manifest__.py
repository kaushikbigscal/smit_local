# -*- coding: utf-8 -*-
{
    "name": "Customer & Employee Timeline",
    "version": "17.0.1.0.0",
    "summary": "Centralized timeline/history for customers and employees.",
    "category": "Tools",
    "author": "Effezient",
    "license": "LGPL-3",
    "depends": ["base", "contacts", 'mail', 'customer_visibility'],
    "data": [
        "security/timeline_groups.xml",
        "security/ir.model.access.csv",
        "views/customer_timeline_view.xml",
        "views/res_config_settings_views.xml",
        "views/employee_timeline_view.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'timeline/static/src/js/timeline_shared.js',
            'timeline/static/src/css/timeline_unified.css',
        ],
    },
    "installable": True,
    "application": False,
}
