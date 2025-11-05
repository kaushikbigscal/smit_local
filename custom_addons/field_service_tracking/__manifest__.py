{
    'name': 'Employee Tracking',
    'version': '1.0',
    'depends': ['base', 'web', 'hr_attendance'],
    'data': [
        "security/ir.model.access.csv",
        'data/ir_rule.xml',
        'views/gps_tracking_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'field_service_tracking/static/src/js/tracker.js',
            'field_service_tracking/static/src/js/route_map.js',
            'field_service_tracking/static/src/xml/gps_tracking_map_template.xml',
            'field_service_tracking/static/src/js/attendance_gps_tracker.js',

        ],
    },
    'installable': True,
    'application': True,
}
