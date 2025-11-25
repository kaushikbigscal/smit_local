{
    'name': 'Product Installation',
    'version': '1.0',
    'category': 'Custom',
    'summary': 'Manage product installations',
    'description': 'Module to manage product installations.',
    'author': 'Effezzint',
    'depends': ['base', 'product','sale','mail','sale_stock','industry_fsm','customer_app','stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_installation_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings.xml',
        'views/res_partner_views.xml',
        'views/distributor_asset_views.xml',
        'views/stock_menu_inherit.xml',
        'views/customer_product_mapping_views.xml',
        'views/portal_template_views.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'product_installation/static/src/js/distributor_stock_components.js',
            'product_installation/static/src/js/chatter_checklist_extension.js',
            'product_installation/static/src/xml/checklist_view.xml',
            # 'product_installation/static/src/js/distributor_stock_search_model.js',
            # 'product_installation/static/src/xml/templates.xml',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
