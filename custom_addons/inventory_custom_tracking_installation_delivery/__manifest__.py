{
    'name': 'Inventory Custom Tracking Installation Delivery ',
    'version': '1.0',
    'category': 'Stock',
    'summary': 'Adds a wizard when validating delivery and give option to create installation task.also add serial number tracking and delivery responsible field.',
    'depends': ['base', 'stock', 'industry_fsm_sale','portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/amc_security.xml',
        'wizards/validate_task_wizard_views.xml',
        'wizards/amc_asset_wizad.xml',
        'views/stock_picking_views.xml',
        'views/amc_contract_views.xml',
        'views/contract_type.xml',
        'views/product_mapping.xml',
        'views/sla_terms.xml',
        'views/quotation.xml',
        'views/invoice.xml',
        'views/schedule_visit.xml',
        'views/res_config_settings.xml',
        'data/cronjob.xml',
        'views/service_call.xml',
        'views/part_history.xml',
        'wizards/part_wizard.xml',
        'report/report.xml',
        'views/report_pdf_template.xml',
        'wizards/amc_contract_renew_wizard.xml',
 


    ],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
