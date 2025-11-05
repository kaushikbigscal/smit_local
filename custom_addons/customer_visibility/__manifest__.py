{
    'name': 'Customer Visibility',
    'version': '1.0',
    'summary': 'Customer Visibility',
    'author': 'Your Name',
    'depends': ['base', 'hr', 'sale', 'account', 'crm','inventory_custom_tracking_installation_delivery'],
    'data': [
        'security/customer_assets_rights.xml',  
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/zone_master_views.xml',
        'views/customer_assginment_views.xml',
    ],
    'installable': True,
    'application': True,
}
