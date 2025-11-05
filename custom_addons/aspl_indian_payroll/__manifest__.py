# -*- coding: utf-8 -*-
###############################################################################
#
# Aspire Softserv Pvt. Ltd.
# Copyright (C) Aspire Softserv Pvt. Ltd.(<https://aspiresoftserv.com>).
#
###############################################################################
{
    "name": "Indian Payroll",
    "category": "Payroll",
    "summary": "Automates payroll, including email payslips, notice period salary holds, and IT declaration management.",
    "version": "17.0.0.1.0",
    "license": "AGPL-3",
    'description': """
        This module add functionality like calculate shortfall, send automatic payslip mail to employee, allow user to hold salary of employee who is in notice period, manage full & final, manage IT Declaration and statement.
    """,
    "author": "Aspire Softserv Pvt. Ltd",
    "website": "https://aspiresoftserv.com",
    "depends": [
        'hr',
        'hr_contract',
        'hr_holidays',
        'om_hr_payroll',
        'hr_attendance',
        'mail',
    ],
    "external_dependencies": {
        'python': [
            'bs4', 'base64', 'xlsxwriter', 'fiscalyear', 'openpyxl'
        ]},
    "data": [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/salary_rule_data.xml',
        'data/salary_structure_data.xml',
        'views/hr_employee_view.xml',
        'views/contract_config_view.xml',
        'views/salary_rule_view.xml',
        'views/salary_rule_category_view.xml',
        'views/salary_structure_view.xml',
        'views/tax_calculations_view.xml',
        'views/it_statement_views.xml',
        'views/hr_payslip_batch_view.xml',
        'views/employee_full_final_view.xml',
        'views/hr_payslip_view.xml',
        'views/res_company_view.xml',
        'views/res_config_settings_views.xml',
        'wizards/payslip_wizard_view.xml',
        'wizards/attendance_shortfall_wizard_view.xml',
        'wizards/hr_payslip_mass_confirm.xml',
        'reports/employee_payslip_report.xml',
        'reports/employee_bulk_mails.xml',
        'reports/payslip_mail_template.xml',
        'reports/employee_full_and_final_report.xml',
    ],
    "assets": {
        'web.assets_backend': [
            'aspl_indian_payroll/static/src/css/it_statement.css',
            'aspl_indian_payroll/static/src/js/it_statement.js',
            'aspl_indian_payroll/static/src/xml/it_statement.xml',
        ],
    },
    "application": True,
    "installable": True,
    'pre_init_hook': '_pre_init_update_rule',
    "maintainer": "Aspire Softserv Pvt. Ltd",
    "support": "odoo@aspiresoftserv.com",
    "images": ['static/description/banner.gif'],
}
