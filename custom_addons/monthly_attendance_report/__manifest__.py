{
    "name": "Attendance Correction & Monthly Attendance Report",
    "version": "1.0",
    "depends": ["base", "hr", "hr_attendance", "hr_holidays", "web"],
    "author": "Effezient",
    "category": "Human Resources",
    "summary": "Generate Monthly Attendance Reports with Excel Export and provide the attendance correction options "
               "where admin can create and update the shortfall attendance.",

    "description": """
        This module allows HR to generate monthly attendance reports 
        with custom columns, filters, and export options. Also allow HR to correct the shortfall attendance.
    """,
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/attendance_correction_rule.xml",
        "views/views.xml",
        "views/monthly_attendance_action.xml",
        "views/attendance_correction_views.xml",

    ],
    "assets": {
        "web.assets_backend": [
            "monthly_attendance_report/static/src/js/custom_list_button.js",
            "monthly_attendance_report/static/src/xml/custom_list_button.xml",
            "web/static/src/core/field_widgets/many2one/*",
            "web/static/src/core/datepicker/*",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
