# -*- coding: utf-8 -*-
{
    'name': "Customer Portal Application",
    'summary': "Short (1 phrase/line) summary of the module's purpose",
    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base','portal','sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/customer_app_security.xml',
        'views/portal_templates.xml',
        'views/portal_template_menu.xml',
        'views/res_company_views.xml',
        'views/views.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            'customer_app/static/src/assets.xml',
            'customer_app/static/src/js/customer_form.js',
            'customer_app/static/src/js/product_search.js',
            'customer_app/static/src/js/payment_form_patch.js',
            'customer_app/static/src/css/customer_portal.css',
            'customer_app/static/src/js/table_sort.js',
            'customer_app/static/src/js/close_datetime.js',
            # 'customer_app/static/src/js/portal_pay_now.js',
            # 'customer_app/static/src/src/js/webpush_sw.js',
            "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css",
            # 'customer_app/static/src/js/custom_push_notification.js',
            # "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js",
            # "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css",

        ],
    },
    # 'uninstall_hook': 'remove_feedback_menu',
# 'post_init_hook': 'post_init_patch',
}

