# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
{
    'name': 'Send service call changes via WhatsApp',
    'version': '17.0.1.0.0',
    'category': 'Service Call',
    'summary': 'This module facilitates sending POS receipts and invoices '
               'through WhatsApp during POS sessions.',
    'description': 'This module enables seamless integration between '
                   'point-of-sale systems and WhatsApp, allowing businesses '
                   'to effortlessly send receipts and invoices to customers '
                   'during transactions. By streamlining communication channels,'
                   ' it enhances customer engagement and convenience in retail '
                   'interactions.',
    'author': 'Mukesh',
    'company': 'Yourcompany',
    'maintainer': 'Your Company',
    'depends': ['point_of_sale'],
    'data': [
        # 'security/ir_rule.xml',
        'security/pos_receipt_invoice_send_whatsapp_groups.xml',
        'security/ir.model.access.csv',
        'views/configuration_manager_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/whatsapp_message_views.xml',
        'wizard/whatsapp_authenticate_views.xml',
	'views/pos_order_line_views.xml',
        'views/whatsapp_template_views.xml',
        # 'data/init_data.xml'
	
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'call_stage_changes_send_whatsapp/static/src/xml/partner_line_templates.xml',
            'call_stage_changes_send_whatsapp/static/src/xml/receipt_screen_templates.xml',
            'call_stage_changes_send_whatsapp/static/src/xml/payment_screen_templates.xml',
            'call_stage_changes_send_whatsapp/static/src/js/ReceiptScreen.js',
            'call_stage_changes_send_whatsapp/static/src/total_sales/total_sales.js',
            'call_stage_changes_send_whatsapp/static/src/total_sales/total_sales.scss',
            'call_stage_changes_send_whatsapp/static/src/total_sales/total_sales.xml',
            'call_stage_changes_send_whatsapp/static/src/customer_creation_button/customer_creation_button.js',
            'call_stage_changes_send_whatsapp/static/src/customer_creation_button/customer_creation_button.xml',
            'call_stage_changes_send_whatsapp/static/src/customer_creation_button/customer_creation_button.scss',
            'call_stage_changes_send_whatsapp/static/src/apps/screens/product_screen/fix_discount_button/fix_discount_button.xml',
            'call_stage_changes_send_whatsapp/static/src/apps/screens/product_screen/fix_discount_button/fix_discount_button.js',
            'call_stage_changes_send_whatsapp/static/src/apps/store/models.js',
            'call_stage_changes_send_whatsapp/static/src/apps/screens/product_screen/orderline/orderline.xml',
            'call_stage_changes_send_whatsapp/static/src/xml/Chrome.xml',
        ],
        # 'web.assets_backend': [
        # ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
