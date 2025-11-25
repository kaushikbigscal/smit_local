import uuid

from odoo import fields, http, _
from odoo.http import request, _logger, Response
from datetime import date, datetime, timedelta
from collections import OrderedDict, defaultdict
from odoo.tools import format_date, format_datetime
import json
import pytz
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.payment import utils as payment_utils
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.addons.payment.controllers.portal import PaymentPortal
from dateutil.relativedelta import relativedelta
from odoo.fields import Date
from ..utils import is_fsm_installed


class PortalHomePage(http.Controller):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        values['fsm_installed'] = is_fsm_installed(request.env)
        return values

    # def _prepare_sale_portal_rendering_values(self, quotation_page=False, **kwargs):
    #     values = super()._prepare_sale_portal_rendering_values(quotation_page=quotation_page, **kwargs)
    #
    #     # Only modify if we are on quotation page
    #     if quotation_page:
    #         partner = request.env.user.partner_id
    #
    #         domain = [
    #             ('partner_id', '=', partner.id),
    #             '|',
    #                 ('state', '=', 'sent'),  # normal quotations
    #                 '&',
    #                     ('state', '=', 'sale'),
    #                     ('invoice_status', 'in', ['to invoice', 'in_payment'])  # partially paid
    #         ]
    #
    #         quotations = request.env['sale.order'].sudo().search(domain, order='create_date desc')
    #         values['quotations'] = quotations
    #         values['quotation_count'] = len(quotations)
    #     return values

    @http.route(['/my/home', '/my'], type='http', auth="user", website=True)
    def portal_my_home(self, **kwargs):
        # Get current website
        # website = request.website
        user = request.env.user
        partner = user.partner_id
        today = date.today()
        # Fetch the 5 most recently created products
        recent_products = request.env['product.product'].sudo().search(
            [], order='create_date desc', limit=2)

        featured_products = request.env['product.product'].sudo().search(
            [], order='create_date', limit=2)

        # Check if ecommerce is installed
        ecom_installed = request.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'website_sale'),
            ('state', '=', 'installed'),
        ]) > 0
        # quotation_domain = [
        #     ('partner_id', '=', partner.id),
        #     '|',
        #     ('state', '=', 'sent'),  # Normal quotations
        #     '&',  # Partially paid quotations
        #     ('state', '=', 'sale'),
        #     ('invoice_status', 'in', ['to invoice', 'in_payment'])
        # ]
        # quotation = request.env['sale.order'].sudo().search(
        #     quotation_domain,
        #     order='create_date desc',
        #     limit=2
        # )
        #
        # quotation_count = request.env['sale.order'].sudo().search_count(
        #     quotation_domain
        # )
        quotation_count = request.env['sale.order'].search_count([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sent'),
        ])

        quotation = request.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sent'),
        ], order='create_date desc', limit=2)

        pending_quotation_count = request.env['sale.order'].search_count([
            ('partner_id', '=', partner.id),
            ('state', 'not in', ['sale', 'draft'])
        ])
        # pending_quotation_count = request.env['sale.order'].search_count(quotation_domain)

        assigned_calls = []
        pending_ticket_count = 0

        if is_fsm_installed(request.env):
            assigned_calls = request.env['project.task'].sudo().search([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True)
            ], order="create_date desc", limit=2)

            pending_ticket_count = request.env['project.task'].sudo().search_count([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True),
                ('stage_id.name', '=', 'Pending')
            ])

        # Safely handle amc.contract
        contract_count = 0
        contract_renewal_message = "No contracts found"
        is_expired = False

        if 'amc.contract' in request.env.registry.models:
            my_contract = request.env['amc.contract'].sudo().search([
                ('partner_id', '=', partner.id),
            ], order="create_date desc", limit=2)
            all_contract = request.env['amc.contract'].sudo().search([
                ('partner_id', '=', partner.id),
            ], order="create_date desc")
            contract_count = len(all_contract)
            contract_renewal_message = "No contracts found"

            if all_contract:
                end_date = all_contract[0].end_date
                today = date.today()
                if end_date and end_date > today:
                    delta = relativedelta(end_date, today)
                    if delta.years == 0 and delta.months == 0:
                        contract_renewal_message = "Expires this month"
                    else:
                        months_remaining = delta.years * 12 + delta.months
                        contract_renewal_message = f"Renewal in {months_remaining} month{'s' if months_remaining != 1 else ''}"
                else:
                    contract_renewal_message = "Expired"
                    is_expired = True
        else:
            all_contract = request.env['ir.model'].browse()  # or just []

        mappings = []

        if 'customer.product.mapping' in request.env.registry.models:
            mappings = request.env['customer.product.mapping'].sudo().search([
                ('customer_id', '=', partner.id)
            ], order='create_date desc', limit=2)

        # Fetch featured products for slider - using product.template
        domain = [
            ('sale_ok', '=', True),  # Only products that can be sold
        ]

        # domain_asset = [
        #     ('customer_id', '=', partner.id),
        #     '|', ('start_date', '=', False), ('start_date', '<=', today),
        #     '|', ('end_date', '=', False), ('end_date', '>=', today)
        # ]
        #
        # active_asset_count = 0
        # if 'customer.product.mapping' in request.env.registry.models:
        #     active_asset_count = request.env['customer.product.mapping'].sudo().search_count(domain_asset)

        # Step 1: Find all active assets
        domain_asset = [
            ('customer_id', '=', partner.id),
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date', '=', False), ('end_date', '>=', today)
        ]

        active_assets = request.env['customer.product.mapping'].sudo().search(domain_asset)
        active_asset_count = len(active_assets)

        # Step 2: Find assets which have tickets (under service)
        # under_service_assets = request.env['project.task'].sudo().search([
        #     ('partner_id', '=', partner.id),
        #     ('customer_product_id', 'in', active_assets.ids),  # adjust field name if different
        #     ('stage_id.name', '!=', 'Done')  # optional: exclude closed tickets
        # ]).mapped('customer_product_id')  # get asset ids linked with tickets
        done_stages = request.env['project.task.type'].sudo().search(
            [('name', 'in', ['Done', 'Cancelled', 'Resolved'])]
        )

        # Get number of tickets (tasks) under service
        # under_service_count = request.env['project.task'].sudo().search_count([
        #     ('partner_id', '=', partner.id),
        #     ('customer_product_id', 'in', active_assets.ids),
        #     ('stage_id', 'not in', done_stages.ids),
        # ])
        # Get distinct asset IDs that have at least one open (not done) task
        under_service_ids = request.env['project.task'].sudo().search([
            ('partner_id', '=', partner.id),
            ('customer_product_id', 'in', active_assets.ids),
            ('stage_id', 'not in', done_stages.ids),
        ]).mapped('customer_product_id.id')

        # Count of assets under service
        under_service_count = len(set(under_service_ids))

        # Assets still operational (all - assets that have at least one ticket)
        assets_with_tickets = request.env['project.task'].sudo().search([
            ('partner_id', '=', partner.id),
            ('customer_product_id', 'in', active_assets.ids),
            ('stage_id', 'not in', done_stages.ids),
        ]).mapped('customer_product_id.id')

        operational_count = active_asset_count - len(set(assets_with_tickets)) if active_asset_count else 0

        # Step 3: Prepare the status text
        if active_asset_count == 0:
            asset_status_message = "No assets"
        else:
            asset_status_message = f"{under_service_count} under service, {operational_count} operational"

        featured_categories = request.env['product.category'].sudo().search([
            ('display_in_catalog_category', '=', True)
        ])

        if featured_categories:
            # Get all products under these categories and subcategories
            featured_products = request.env['product.template'].sudo().search([
                ('categ_id', 'child_of', featured_categories.ids),
                ('display_in_catalog', '=', False)
            ])
            # Set them as featured
            featured_products.write({'display_in_catalog': True})
        # Add website-specific filtering if website_sale is installed
        if ecom_installed:
            domain.append(('is_published', '=', True))
            domain.append(('website_published', '=', True))

        domain.append(('display_in_catalog', '=', True))
        featured_products_slider = request.env['product.template'].sudo().search(
            domain,
            order='create_date desc',
            limit=6
        )

        company = request.env.company.sudo()
        banner_images = company.image
        for a in banner_images:
            print(f"ATTACHMENT → ID: {a.id}, Name: {a.name}, Has Data: {bool(a.datas)}")
        attachments = request.env['ir.attachment'].sudo().search([
            ('id', 'in', [5927, 5928])  # replace with actual image IDs
        ])

        # Prepare values for template
        values = {
            'ecom_installed': ecom_installed,
            'show_shop_menu': ecom_installed,
            'quotation': quotation,
            'quotation_count': quotation_count,
            'pending_quotation_count': pending_quotation_count,
            'recent_products': recent_products,
            'featured_products': featured_products,
            'featured_products_slider': featured_products_slider,
            'assigned_calls': assigned_calls,
            'pending_ticket_count': pending_ticket_count,
            'mappings': mappings,
            'my_contract': my_contract,
            'contract_count': contract_count,
            'is_expired': is_expired,
            'contract_renewal_message': contract_renewal_message,
            'active_asset_count': active_asset_count,
            'under_service_count': under_service_count,
            'operational_count': operational_count,
            'asset_status_message': asset_status_message,
            'company': company,
            'banner_images': banner_images,
            'fsm_installed': is_fsm_installed(request.env),
            'enable_scanner': company.enable_qr_code_scanner,

        }
        # Call original rendering and inject context
        response = request.render("portal.portal_my_home", values)
        print(response)
        return response

    @http.route(['/product/<int:product_id>'], type='http', auth="user", website=True)
    def product_detail(self, product_id, **kwargs):
        product_template = request.env['product.template'].sudo().browse(product_id)
        if not product_template or not product_template.exists():
            return request.not_found()

        return request.render('customer_app.product_custom_page', {
            'product': product_template,
            'page_name': "All Products",
            'product_name': product_template.name,
        })

    @http.route(['/products'], type='http', auth='user', website=True)
    def custom_products_page(self, page=1, q='', sort='date', **kwargs):
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
        domain = [('sale_ok', '=', True)]
        if q:
            domain += ['|', ('name', 'ilike', q), ('default_code', 'ilike', q)]

        sort_map = {
            'price_asc': 'list_price asc',
            'price_desc': 'list_price desc',
            'date': 'create_date desc'
        }

        sort_by = sort_map.get(sort, 'create_date desc')
        per_page = 12
        offset = (page - 1) * per_page

        Product = request.env['product.product'].sudo()
        products = Product.search(domain, order=sort_by, limit=per_page, offset=offset)
        total_products = Product.search_count(domain)
        total_pages = -(-total_products // per_page)

        return request.render('customer_app.product_grid_page', {
            'products': products,
            'search_term': q,
            'sort_by': sort,
            'page': page,
            'page_name': "All Product",
            'total_pages': total_pages,
        })

    @http.route('/product/autocomplete', type='json', auth='public', website=True, csrf=False)
    def product_autocomplete(self, search_term='', **kwargs):
        products = request.env['product.product'].sudo().search([
            ('sale_ok', '=', True),
            ('name', 'ilike', search_term)
        ], limit=10)

        return [{
            'name': p.name,
            'url': '/product/%s' % p.id,  # or use slug if SEO route enabled
            'image_url': '/web/image/product.product/%s/image_128' % p.id
        } for p in products]

    # Controller code for ticket form view
    @http.route(['/my/ticket/<int:ticket_id>'], type='http', auth='user', website=True)
    def view_ticket(self, ticket_id, **kw):
        env = request.env
        user = env.user
        partner = user.partner_id
        ticket = request.env['project.task'].sudo().browse(ticket_id)

        service_charges = []
        total_charge = 0
        # --- Get assignee employee mobile ---
        phone = ''
        if ticket.user_ids:
            assignee_user = ticket.user_ids[:1]  # get first assigned user safely
            assignee_employee = env['hr.employee'].sudo().search([('user_id', '=', assignee_user.id)], limit=1)
            phone = assignee_employee.mobile_phone or assignee_employee.work_phone or ''

        if ticket.call_type.name == 'Chargeable':
            service_charges = request.env['service.charge'].sudo().search([
                ('task_id', '=', ticket.id)
            ])
            total_charge = sum(service_charges.mapped('amount'))
        # if ticket.call_type == 'chargeable':
        #     service_charges = request.env['service.charge'].sudo().search([
        #         ('task_id', '=', ticket.id)
        #     ])
        #     total_charge = sum(charge['amount'] for charge in service_charges)
        if not ticket.exists():
            return request.not_found()

        if not is_fsm_installed(env):
            return request.render("customer_app.ticket_form_view", {
                'ticket': ticket,
                'page_name': 'Ticket',
                'prev_record': None,
                'next_record': None,
                'stages': [],  # empty stages
            })
        #  Use only customer-related tickets from session or fallback
        ticket_id_list = request.session.get('my_ticket_list') or []
        if ticket.id not in ticket_id_list:
            ticket_id_list = request.env['project.task'].sudo().search([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True)
            ], order="id").ids

        prev_ticket_id = next_ticket_id = None
        if ticket.id in ticket_id_list:
            index = ticket_id_list.index(ticket.id)
            if index > 0:
                prev_ticket_id = ticket_id_list[index - 1]
            if index < len(ticket_id_list) - 1:
                next_ticket_id = ticket_id_list[index + 1]

        fsm_stages = request.env['project.task.type'].sudo().search([
            ('project_ids.is_fsm', '=', True)
        ], order="sequence")

        # Deduplicate by stage name
        unique_stages_by_name = OrderedDict()
        for stage in fsm_stages:
            if stage.name not in unique_stages_by_name:
                unique_stages_by_name[stage.name] = stage

        stage_list = list(unique_stages_by_name.values())
        selected_stage = stage_list[0] if stage_list else False

        if not selected_stage:
            return request.render('website.404')
        #
        # chatter_attachments = ticket.attachment_ids
        #
        # # ir.attachment attachments
        # ir_attachments = request.env['ir.attachment'].sudo().search([
        #     ('res_model', '=', 'project.task'),
        #     ('res_id', '=', ticket.id),
        # ])
        #
        # # merge both (avoid duplicates by id)
        # all_attachments = (chatter_attachments | ir_attachments).sudo()

        attachments = []

        chatter_attachments = ticket.attachment_ids.sudo()
        print("chatter attachment:", chatter_attachments)
        ir_attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', ticket.id),
        ])
        all_attachments = (chatter_attachments | ir_attachments).sudo()

        print("DEBUG: all_attachments", all_attachments.ids)

        for att in all_attachments:
            print("DEBUG: processing attachment", att.id, att.name)
            if not att.access_token:
                print("DEBUG: generating access_token for", att.id)
                att.sudo().write({'access_token': str(uuid.uuid4())})
        attachments = all_attachments

        print("Attachments", attachments)
        payment_values = TicketPaymentPortal()._get_ticket_payment_values(ticket)
        return request.render("customer_app.ticket_form_view", {
            'ticket': ticket,
            'page_name': 'Ticket',
            'prev_record': f'/my/ticket/{prev_ticket_id}' if prev_ticket_id else None,
            'next_record': f'/my/ticket/{next_ticket_id}' if next_ticket_id else None,
            'stages': stage_list,
            'service_charges': service_charges,
            'total_charge': total_charge,
            'phone': phone,
            'attachments': attachments,
            **payment_values,
        })

    @http.route(['/my/service/<int:task_id>/pay'], type='http', auth='user', website=True)
    def service_payment_page(self, task_id, **kwargs):
        task = request.env['project.task'].sudo().browse(task_id)
        if not task.exists() or task.partner_id != request.env.user.partner_id:
            return request.render("website.404")

        amount = task.remaining_amount
        if amount <= 0:
            return request.render("customer_app.payment_done_template", {"task": task})

        partner = request.env.user.partner_id
        currency = task.currency_id
        company = task.company_id

        providers = request.env['payment.provider'].sudo()._get_compatible_providers(
            company.id, partner.id, amount, currency_id=currency.id
        )
        tokens = request.env['payment.token'].sudo()._get_available_tokens(providers.ids, partner.id)
        methods = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers.ids, partner.id, currency_id=currency.id
        )

        values = {
            'task': task,
            'amount': amount,
            'currency': currency,
            'partner_id': partner.id,
            'providers_sudo': providers,
            'tokens_sudo': tokens,
            'payment_methods_sudo': methods,
            'transaction_route': f"/my/service/{task.id}/transaction",
            'landing_route': f"/my/service/{task.id}",
            'access_token': task._portal_ensure_token(),
        }
        return request.render("customer_app.service_charge_payment_modal", values)

    @http.route(['/my/service/<int:task_id>/transaction'], type='json', auth='user', website=True)
    def service_create_transaction(self, task_id, access_token=None, **kwargs):
        task = request.env['project.task'].sudo().browse(task_id)
        if not task.exists():
            raise ValidationError(_("Invalid service task"))

        partner_id = request.env.user.partner_id.id
        if not payment_utils.check_access_token(
                access_token, partner_id, task.remaining_amount, task.currency_id.id
        ):
            raise ValidationError(_("Invalid token"))

        kwargs.update({
            'partner_id': partner_id,
            'currency_id': task.currency_id.id,
            'company_id': task.company_id.id,
            'task_id': task.id,
        })

        tx = request.env['payment.transaction'].sudo()._create_transaction(
            custom_create_values={'task_id': task.id}, **kwargs
        )

        return tx._get_processing_values()

    @http.route(['/my/view'], type='http', auth='user', website=True)
    def my_tickets(self, sortby='name', filterby='all', groupby='', search='', **kwargs):
        env = request.env
        user = env.user
        partner = user.partner_id

        # Check if FSM is installed
        if not is_fsm_installed(env):
            return request.render('customer_app.ticket_list_view', {
                'calls': [],
                'open_tickets': [],
                'page_name': 'All Tickets',
                'grouped_calls': {},
                'search': search,
                'filterby': filterby,
                'groupby': groupby,
                'search_in': 'name',
                'searchbar_inputs': [],
                'searchbar_filters': {},
                'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
                'searchbar_groupby': {},
                'default_url': '/my/view',
            })

        Task = env['project.task'].sudo()
        excluded_names = ['Done', 'Cancelled', 'Resolved']

        domain = [('partner_id', '=', partner.id)]
        if 'is_fsm' in Task._fields:
            domain.append(('is_fsm', '=', True))

        # --- Search ---
        if search:
            search_domain = ['|', '|', '|', '|', '|', '|',
                             ('name', 'ilike', search)]
            if 'sequence_fsm' in Task._fields:
                search_domain.append(('sequence_fsm', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))

            if 'customer_product_id' in Task._fields:
                search_domain.append(('customer_product_id.product_id.name', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))
            if 'user_ids' in Task._fields:
                search_domain.append(('user_ids.name', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))
            if 'create_date' in Task._fields:
                search_domain.append(('create_date', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))
            if 'date_deadline' in Task._fields:
                search_domain.append(('planned_date_begin', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))
            if 'stage_id' in Task._fields:
                search_domain.append(('stage_id.name', 'ilike', search))
            else:
                search_domain.append(('name', 'ilike', search))

            domain += search_domain

        # --- Base Ticket Search ---
        calls = Task.search(domain)

        # --- Sortings ---
        sortings = {
            'name': {'label': 'Call Name', 'order': 'name asc'},
            'stage': {'label': 'Stage', 'order': 'stage_id asc'},
            'recent': {'label': 'Newest', 'order': 'create_date desc'},
            'expected': {'label': 'Expected Date', 'order': 'date_deadline asc'},
            'creation': {'label': 'Creation Date', 'order': 'create_date asc'},
            'ticket': {'label': 'Ticket Number', 'order': 'sequence_fsm asc'},
            'assignee': {'label': 'Assignee', 'order': 'user_ids asc'},
        }
        order = sortings.get(sortby, sortings['recent'])['order']
        calls = calls.sorted(
            key=lambda c: getattr(c, order.split()[0], '') or '',
            reverse='desc' in order
        )

        # --- Filters ---
        filters = {
            'all': {'label': 'All', 'domain': []},
            'open_calls': {'label': 'Open Calls',
                           'domain': [('stage_id.name', 'not in', ['Done', 'Canceled', 'Resolved'])]},
            'closed_calls': {'label': 'Close Calls',
                             'domain': [('stage_id.name', 'in', ['Done', 'Canceled', 'Resolved'])]},
        }

        for assignee in calls.mapped('user_ids'):
            filters[f'user_{assignee.id}'] = {
                'label': f'Assignee: {assignee.name}',
                'domain': [('user_ids', 'in', assignee.id)],
            }

        filter_domain = filters.get(filterby, filters['all'])['domain']
        if filter_domain:
            calls = calls.filtered_domain(filter_domain)

        # --- Grouping ---
        grouped_calls = {}
        if groupby == 'stage':
            for call in calls:
                stage_name = call.stage_id.name if call.stage_id else "No Stage"
                grouped_calls.setdefault(stage_name, []).append(call)

        elif groupby == 'assignee':
            for call in calls:
                assignee_name = call.user_ids.name if call.user_ids else "Unassigned"
                grouped_calls.setdefault(assignee_name, []).append(call)

        elif groupby == 'call_type':
            for call in calls:
                call_type_name = call.call_type.name if call.call_type else "No Type"
                grouped_calls.setdefault(call_type_name, []).append(call)

        # --- Combine Filter & GroupBy for Frontend Dropdown ---
        combined_options = {}
        for key, val in filters.items():
            combined_options[f'f_{key}'] = {
                'label': f"{val['label']}",
                'filterby': key,
                'groupby': groupby,
            }

        for key, val in {
            'stage': {'label': 'Stage'},
            'assignee': {'label': 'Assignee'},
            'call_type': {'label': 'Call Type'},
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"{val['label']}",
                'groupby': key,
                'filterby': filterby,
            }

        open_tickets = Task.search([('partner_id', '=', partner.id)]).filtered(
            lambda t: t.stage_id and t.stage_id.name not in excluded_names
        )

        mapping_ids = request.env['customer.product.mapping'].sudo().search([
            ('customer_id', '=', partner.id),
        ], limit=1)

        return request.render('customer_app.ticket_list_view', {
            'calls': calls,
            'open_tickets': open_tickets,
            'page_name': 'All Tickets',
            'grouped_calls': grouped_calls,
            'search': search,
            'filterby': filterby,
            'groupby': groupby,
            'search_in': 'name',
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_filters': filters,
            'searchbar_groupby': {
                'none': {'input': 'none', 'label': 'None'},
                'stage': {'input': 'stage', 'label': 'Stage'},
                'assignee': {'input': 'assignee', 'label': 'Assignee'},
                'call_type': {'input': 'call_type', 'label': 'Call Type'},
            },
            'searchbar_combined': combined_options,
            'default_url': '/my/view',
            'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'has_active_assets': bool(mapping_ids),
        })

    @http.route(['/my/assets', '/my/contract/<int:contract_id>/assets'], type='http', auth='user', website=True)
    def list_products(self, contract_id=None, sortby='name', filterby='all', groupby='', search='', **kwargs):
        env = request.env
        partner = env.user.partner_id

        #  Check model availability
        if 'customer.product.mapping' not in env.registry.models:
            return request.render("website.404")  # or your custom "not available" page

        Mapping = env['customer.product.mapping'].sudo()
        contract = None
        domain = [('customer_id', '=', partner.id)]

        if contract_id and 'amc.contract' in env.registry.models:
            contract = env['amc.contract'].sudo().browse(contract_id)
            domain.append(('contract_id', '=', contract_id))

        # Search
        if search:
            domain += ['|', '|', '|', '|', '|',
                       ('product_id.name', 'ilike', search),
                       ('product_id.default_code', 'ilike', search),
                       ('serial_number_ids', 'ilike', search),
                       ('status', 'ilike', search),
                       ('start_date', 'ilike', search),
                       ('end_date', 'ilike', search),
                       ]

        mappings = Mapping.search(domain)

        # Prepare product data
        products_data = []
        for mapping in mappings:
            product = mapping.product_id
            status_selection = dict(mapping.fields_get(['status'])['status']['selection'])
            products_data.append({
                'mapping_id': mapping.id,
                'unique_number': mapping.unique_number,
                'name': product.name,
                # 'status': mapping.status,
                'status': status_selection.get(mapping.status, 'N/A'),
                'start_date': mapping.start_date,
                'end_date': mapping.end_date,
                'categ_name': product.categ_id.name if product.categ_id else 'Uncategorized',
                'serial_number_ids': [{'name': sn.name} for sn in mapping.serial_number_ids],
            })

        # Sorting
        sortings = {
            'name': {'label': 'Name', 'order': 'name'},
            'recent': {'label': 'Newest', 'order': 'start_date'},
        }
        sort_key = sortings.get(sortby, sortings['name'])['order']
        products_data = sorted(products_data, key=lambda p: p.get(sort_key) or '')
        # Filters
        filters = {
            'all': {'label': 'All', 'domain': []},
            'under_service': {
                'label': 'Under Service',
                'domain': None  # will handle separately
            }
        }

        # Dynamic filters by category
        for cat in set(p['categ_name'] for p in products_data):
            filters[f'cat_{cat}'] = {
                'label': f'Category: {cat}',
                'domain': lambda prod, c=cat: prod['categ_name'] == c
            }

        # Dynamic filters by status
        for stat in set(p['status'] for p in products_data):
            filters[f'status_{stat}'] = {
                'label': f'Status: {stat}',
                'domain': lambda prod, s=stat: prod['status'] == s
            }

        # Apply selected filter
        if filterby == 'under_service':
            done_stages = env['project.task.type'].sudo().search([
                ('name', 'in', ['Done', 'Cancelled', 'Resolved'])
            ])

            tasks = env['project.task'].sudo().search([
                ('partner_id', '=', partner.id),
                ('customer_product_id', 'in', mappings.ids),
                ('stage_id', 'not in', done_stages.ids),
            ])
            under_service_ids = tasks.mapped('customer_product_id.id')

            products_data = [p for p in products_data if p['mapping_id'] in under_service_ids]

        elif callable(filters.get(filterby, {}).get('domain')):
            products_data = list(filter(filters[filterby]['domain'], products_data))

        # Grouping
        grouped_products = {}
        if groupby == 'category':
            for product in products_data:
                cat_name = product['categ_name']
                grouped_products.setdefault(cat_name, []).append(product)

        elif groupby == 'status':
            for product in products_data:
                status = product['status']
                grouped_products.setdefault(status, []).append(product)

        # Combine filter and groupby
        combined_options = {}
        for key, val in filters.items():
            combined_options[f'f_{key}'] = {
                'label': f"{val['label']}",
                'filterby': key,
                'groupby': groupby,
            }

        for key, val in {
            'category': {'label': 'Category'},
            'status': {'label': 'Status'},
            'source_type': {'label': 'Source Type'},
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"{val['label']}",
                'groupby': key,
                'filterby': filterby,
            }

        return request.render("customer_app.product_list_view", {
            'products': products_data,
            'grouped_products': grouped_products,
            'page_name': 'My Assets',
            'contract': contract,
            'show_products': bool(contract_id),
            'search': search,
            'filterby': filterby,
            'groupby': groupby,
            'search_in': 'name',
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_filters': filters,
            'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'searchbar_groupby': {
                'none': {'input': '', 'label': 'None'},
                'category': {'input': 'category', 'label': 'Category'},
                'status': {'input': 'status', 'label': 'Status'},
                'source_type': {'input': 'source_type', 'label': 'Source Type'},
            },
            'searchbar_combined': combined_options,
            'default_url': '/my/assets',
        })

    @http.route(['/my/asset/<int:mapping_id>'], type='http', auth="user", website=True)
    def view_product_detail(self, mapping_id, **kwargs):
        user = request.env.user
        partner = user.partner_id
        if 'customer.product.mapping' not in request.env:
            return request.render("website.404")
        # Get the full list of product mappings for the logged-in partner
        mapping_ids = request.env['customer.product.mapping'].sudo().search([
            ('customer_id', '=', partner.id)
        ], order='id')

        # Find the currently requested mapping
        mapping = mapping_ids.filtered(lambda m: m.id == mapping_id)
        if not mapping:
            return request.render("portal.404")
        mapping = mapping[0]

        # For next/prev navigation based on mapping ID
        mapping_id_list = [rec.id for rec in mapping_ids]
        prev_id = next_id = None
        if mapping_id in mapping_id_list:
            index = mapping_id_list.index(mapping_id)
            if index > 0:
                prev_id = mapping_id_list[index - 1]
            if index < len(mapping_id_list) - 1:
                next_id = mapping_id_list[index + 1]

        coverage_note = ''
        today = datetime.today().date()
        if mapping.end_date:
            if mapping.end_date < today:
                coverage_note = f"Expired on {format_date(request.env, mapping.end_date, date_format='dd/MM/yyyy')}"
            elif mapping.end_date <= today + timedelta(days=30):
                coverage_note = f"Going out of Coverage Soon {format_date(request.env, mapping.end_date, date_format='dd/MM/yyyy')}"

        return request.render('customer_app.customer_product_detail_form_view', {
            'mapping': mapping,
            'page_name': 'Assets',
            'prev_record': f'/my/asset/{prev_id}' if prev_id else None,
            'next_record': f'/my/asset/{next_id}' if next_id else None,
            'format_date': lambda date: format_date(request.env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'coverage_note': coverage_note,
        })

    @http.route(['/my/open/ticket'], type='http', auth='user', website=True)
    def list_open_tickets(self, sortby='recent', filterby='all', groupby='', search='', **kwargs):
        env = request.env
        user = env.user
        partner = user.partner_id

        # Check if 'is_fsm' field exists
        Task = env['project.task']
        if 'is_fsm' not in Task._fields:
            # industry_fsm not installed: show nothing or a placeholder page
            return request.render("website.404")  # or render a custom message

        # FSM logic starts here
        excluded_names = ['Done', 'Cancelled', 'Resolved']
        domain = [
            ('is_fsm', '=', True),
            ('partner_id', '=', partner.id),
        ]

        sortings = {
            'name': {'label': 'Call Name', 'order': 'name asc'},
            'stage': {'label': 'Stage', 'order': 'stage_id asc'},
            'recent': {'label': 'Newest', 'order': 'create_date desc'},
        }
        order = sortings.get(sortby, sortings['recent'])['order']

        if search:
            domain += ['|', '|', '|', '|', '|', '|',
                       ('name', 'ilike', search),
                       ('sequence_fsm', 'ilike', search),
                       ('customer_product_id.product_id.name', 'ilike', search),
                       ('user_ids.name', 'ilike', search),
                       ('create_date', 'ilike', search),
                       ('planned_date_begin', 'ilike', search),
                       ('stage_id.name', 'ilike', search)
                       ]

        all_calls = Task.sudo().search(domain, order=order)

        # Filter by open stages
        valid_tasks = all_calls.filtered(lambda t: t.stage_id and t.stage_id.name not in excluded_names)

        filters = {
            'all': {'label': 'All', 'domain': []},
            'pending': {
                'label': 'Pending',
                'domain': [('stage_id.name', '=', 'Pending')]
            }
        }

        for assignee in valid_tasks.mapped('user_ids'):
            filters[f'user_{assignee.id}'] = {
                'label': f'Assignee: {assignee.name}',
                'domain': [('user_ids', 'in', assignee.id)]
            }

        filter_domain = filters.get(filterby, filters['all'])['domain']
        if filter_domain:
            valid_tasks = valid_tasks.filtered_domain(filter_domain)

        grouped_calls = {}
        if groupby == 'stage':
            for call in valid_tasks:
                stage_name = call.stage_id.name if call.stage_id else "No Stage"
                grouped_calls.setdefault(stage_name, []).append(call)

        elif groupby == 'assignee':
            for call in valid_tasks:
                assignee_name = call.user_ids.name if call.user_ids else "Unassigned"
                grouped_calls.setdefault(assignee_name, []).append(call)
        elif groupby == 'call_type':
            for call in valid_tasks:
                call_type_name = call.call_type.name if call.call_type else "No Type"
                grouped_calls.setdefault(call_type_name, []).append(call)

        # --- Combine Filter & GroupBy for Frontend Dropdown ---
        combined_options = {}
        for key, val in filters.items():
            combined_options[f'f_{key}'] = {
                'label': f"{val['label']}",
                'filterby': key,
                'groupby': groupby,
            }

        for key, val in {
            'stage': {'label': 'Stage'},
            'assignee': {'label': 'Assignee'},
            'call_type': {'label': 'Call Type'},
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"{val['label']}",
                'groupby': key,
                'filterby': filterby,
            }

        return request.render("customer_app.open_ticket_list_view", {
            'open_tickets': valid_tasks,
            'calls': valid_tasks,
            'grouped_calls': grouped_calls,
            'page_name': 'Open Tickets',
            'search': search,
            'filterby': filterby,
            'groupby': groupby,
            'search_in': 'name',
            'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_filters': filters,
            'searchbar_groupby': {
                'none': {'input': 'none', 'label': 'None'},
                'stage': {'input': 'stage', 'label': 'Stage'},
                'assignee': {'input': 'assignee', 'label': 'Assignee'},
                'call_type': {'input': 'call_type', 'label': 'Call Type'},
            },
            'searchbar_combined': combined_options,
            'default_url': '/my/open/ticket',
            'open_ticket_count': len(valid_tasks),
        })

    @http.route(['/my/active/assets'], type='http', auth='user', website=True)
    def active_list_products(self, sortby='name', filterby='under_service', groupby='', search='', **kwargs):
        partner = request.env.user.partner_id
        today = date.today()

        # Check if the model exists (in case industry_fsm is uninstalled)
        if 'customer.product.mapping' not in request.env:
            return request.render("website.404")  # Or a custom message/page

        # --- Domain base ---
        domain = [('customer_id', '=', partner.id)]

        # --- Search ---
        if search:
            domain += ['|', '|', '|', '|', '|',
                       ('product_id.name', 'ilike', search),
                       ('product_id.default_code', 'ilike', search),
                       ('serial_number_ids', 'ilike', search),
                       ('status', 'ilike', search),
                       ('start_date', 'ilike', search),
                       ('end_date', 'ilike', search),
                       ]

        # --- Date filter: Only active assets
        domain += [
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date', '=', False), ('end_date', '>=', today)
        ]

        mappings = request.env['customer.product.mapping'].sudo().search(domain)

        # --- Build product + mapping data ---
        product_data = []
        for mapping in mappings:
            if mapping.product_id:
                product_data.append({
                    'product': mapping.product_id,
                    'mapping': mapping,
                    'start_date_fmt': format_date(request.env, mapping.start_date,
                                                  date_format='dd/MM/yyyy') if mapping.start_date else 'N/A',
                    'end_date_fmt': format_date(request.env, mapping.end_date,
                                                date_format='dd/MM/yyyy') if mapping.end_date else 'N/A',
                    'status': mapping.status or 'Unknown',
                    'source_type': mapping.source_type or 'Unknown',
                })

        # --- Sortings ---
        sortings = {
            'name': {'label': 'Name', 'order': 'name'},
            'recent': {'label': 'Newest', 'order': 'create_date'},
        }
        order_key = sortings.get(sortby, sortings['name'])['order']
        product_data.sort(key=lambda x: getattr(x['product'], order_key) or '')

        # Filters
        filters = {
            'all': {'label': 'All', 'domain': []},
            'under_service': {
                'label': 'Under Service',
                'domain': None  # will handle separately since it's more complex
            }
        }
        # Dynamic filters by category
        for categ in set(p['product'].categ_id for p in product_data):
            if categ:
                filters[f'cat_{categ.id}'] = {
                    'label': f'Category: {categ.name}',
                    'domain': lambda item: item['product'].categ_id.id == categ.id
                }
        # Dynamic filters by status
        for stat in set(p['status'] for p in product_data):
            filters[f'status_{stat}'] = {
                'label': f'Status: {stat}',
                'domain': lambda prod, s=stat: prod['status'] == s
            }

        # --- Apply selected filter ---
        products_data = product_data

        if filterby == 'under_service':
            done_stages = request.env['project.task.type'].sudo().search(
                [('name', 'in', ['Done', 'Cancelled', 'Resolved'])]
            )

            tasks = request.env['project.task'].sudo().search([
                ('partner_id', '=', partner.id),
                ('customer_product_id', 'in', mappings.ids),  # mappings already active
                ('stage_id', 'not in', done_stages.ids),
            ])

            under_service_ids = tasks.mapped('customer_product_id.id')

            # Check against mapping.id
            products_data = [p for p in product_data if p['mapping'].id in under_service_ids]


        elif callable(filters.get(filterby, {}).get('domain')):
            products_data = list(filter(filters[filterby]['domain'], product_data))

        # Grouping
        grouped_products = {}
        if groupby == 'category':
            for item in products_data:
                cat_name = item['product'].categ_id.name or "Uncategorized"
                grouped_products.setdefault(cat_name, []).append(item)

        elif groupby == 'status':
            for product in products_data:
                status = product['status']
                grouped_products.setdefault(status, []).append(product)

        # Combine filter and groupby
        combined_options = {}
        for key, val in filters.items():
            combined_options[f'f_{key}'] = {
                'label': f"{val['label']}",
                'filterby': key,
                'groupby': groupby,
            }

        for key, val in {
            'category': {'label': 'Category'},
            'status': {'label': 'Status'},
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"{val['label']}",
                'groupby': key,
                'filterby': filterby,
            }

        return request.render("customer_app.active_assets_list_view", {
            'product_data': products_data,
            'grouped_products': grouped_products,
            'page_name': 'Active Assets',
            'search': search,
            'filterby': filterby,
            'groupby': groupby,
            'search_in': 'name',
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_filters': filters,
            'searchbar_groupby': {
                'none': {'input': '', 'label': 'None'},
                'category': {'input': 'category', 'label': 'Category'},
                'status': {'input': 'status', 'label': 'Status'},
            },
            'searchbar_combined': combined_options,
            'default_url': '/my/active/assets',
        })

    @http.route('/get/reason/by/complaint', type='http', auth='user', website=True, csrf=False)
    def get_reason_codes_by_complaint_types(self, **kw):
        try:
            raw_data = request.httprequest.get_data().decode('utf-8')
            data = json.loads(raw_data)
        except Exception as e:
            return Response("Invalid JSON", status=400)

        complaint_type_names = data.get('complaint_type_names', [])

        reason_codes = []
        if complaint_type_names:
            domain = [('complaint_type_id.name', 'in', complaint_type_names)]
            reason_code_recs = request.env['reason.code'].sudo().search(domain)
            reason_codes = [{'id': rc.id, 'name': rc.name} for rc in reason_code_recs]

        return Response(json.dumps({'reason_codes': reason_codes}), content_type='application/json;charset=utf-8')

    # --- Create Ticket Form ---
    # @http.route('/my/ticket/create', type='http', auth='user', website=True)
    # def call_form(self, **kw):
    #     company = request.env.company
    #     user = request.env.user
    #     partner = user.partner_id
    #     default_product_id = int(kw.get('product_id', 0))
    #
    #     # Safe: Check if model exists
    #     if 'customer.product.mapping' not in request.env:
    #         return request.render("website.404")
    #
    #     mappings = request.env['customer.product.mapping'].sudo().search([
    #         ('customer_id', '=', partner.id)
    #     ])
    #
    #     # complaint_types = request.env['complaint.type'].sudo().search([])
    #     complaint_types = request.env['complaint.type'].sudo().search([
    #         ('show_in_portal', '=', True)
    #     ])
    #
    #     reason_codes = request.env['reason.code'].sudo().search([])
    #
    #     return request.render('customer_app.call_form_template', {
    #         'page_name': 'Create Ticket',
    #         'products': mappings,
    #         'complaint_types': complaint_types,
    #         'reason_codes': reason_codes,
    #         'default_product_id': default_product_id,
    #         'enable_scanner': company.enable_qr_code_scanner,
    #     })

    @http.route('/my/ticket/create', type='http', auth='user', website=True)
    def call_form(self, **kw):
        company = request.env.company
        user = request.env.user
        partner = user.partner_id

        # Default values
        default_mapping_id = 0

        product_id = int(kw.get('product_id') or 0)  # product.product ID
        product_mapping_id = int(kw.get('product_mapping_id') or 0)  # customer.product.mapping ID
        serial_number = kw.get('serial_number') or False  # lot/serial number
        # All mappings for this customer
        mappings = request.env['customer.product.mapping'].sudo().search([
            ('customer_id', '=', partner.id)
        ])

        # --- CASE 1: Mapping ID passed directly (QR generated from mapping)
        if product_mapping_id:
            mapping = request.env['customer.product.mapping'].sudo().browse(product_mapping_id)
            if mapping and mapping.customer_id.id == partner.id:
                default_mapping_id = mapping.id
            else:
                # mapping not valid for this customer
                return request.render('customer_app.product_warning_template', {
                    'product_id': product_mapping_id,
                })

        # --- CASE 2: Product ID + serial number passed (QR generated from product)
        elif product_id and serial_number:
            mapping = mappings.filtered(
                lambda m: m.product_id.id == product_id and serial_number in m.serial_number_ids.mapped('name'))
            if mapping:
                default_mapping_id = mapping.id
                selected_serial = mapping.serial_number_ids.filtered(lambda l: l.name == serial_number)
            else:
                return request.render('customer_app.product_warning_template', {
                    'error': f"No mapping found for Product {product_id} with Serial {serial_number}.",
                    'product_id': product_mapping_id,
                })

        # CASE 3: product id only (find first mapping for this product)
        elif product_id:
            mapping = mappings.filtered(lambda m: m.product_id.id == product_id)
            if mapping:
                default_mapping_id = mapping.id

        print("kw product_id:", product_id)
        print("mappings product ids:", mappings.mapped('product_id').ids)
        print("mappings template ids:", mappings.mapped('product_id.product_tmpl_id').ids)

        # Complaint & reason codes
        complaint_types = request.env['complaint.type'].sudo().search([
            ('show_in_portal', '=', True)
        ])
        reason_codes = request.env['reason.code'].sudo().search([])

        return request.render('customer_app.call_form_template', {
            'page_name': 'Create Ticket',
            'products': mappings,
            'complaint_types': complaint_types,
            'reason_codes': reason_codes,
            'default_product_id': default_mapping_id,  # Always mapping.id
            # 'enable_scanner': company.enable_qr_code_scanner,
        })

    # @http.route('/my/ticket/create', type='http', auth='user', website=True)
    # def call_form(self, **kw):
    #     company = request.env.company
    #     user = request.env.user
    #     partner = user.partner_id
    #
    #     # URL params
    #     product_id = int(kw.get('product_id') or 0)  # product.product ID
    #     product_mapping_id = int(kw.get('product_mapping_id') or 0)  # customer.product.mapping ID
    #     serial_number = kw.get('serial_number') or False  # lot/serial number
    #
    #     default_mapping_id = 0
    #     selected_serial = False
    #
    #     # All mappings for this customer
    #     mappings = request.env['customer.product.mapping'].sudo().search([
    #         ('customer_id', '=', partner.id)
    #     ])
    #
    #     # --- CASE 1: Mapping ID passed
    #     if product_mapping_id:
    #         mapping = request.env['customer.product.mapping'].sudo().browse(product_mapping_id)
    #         if mapping and mapping.customer_id.id == partner.id:
    #             default_mapping_id = mapping.id
    #             if serial_number:
    #                 lot = mapping.serial_number_ids.filtered(lambda l: l.name == serial_number)
    #                 if lot:
    #                     selected_serial = lot
    #                 else:
    #                     return request.render('customer_app.product_warning_template', {
    #                         'error': f"Serial {serial_number} not valid for this mapping."
    #                     })
    #         else:
    #             return request.render('customer_app.product_warning_template', {
    #                 'error': "Mapping not valid for this customer.",
    #             })
    #
    #     # --- CASE 2: Product ID + Serial Number passed
    #     elif product_id and serial_number:
    #         mapping = mappings.filtered(
    #             lambda m: m.product_id.id == product_id and serial_number in m.serial_number_ids.mapped('name'))
    #         if mapping:
    #             default_mapping_id = mapping.id
    #             selected_serial = mapping.serial_number_ids.filtered(lambda l: l.name == serial_number)
    #         else:
    #             return request.render('customer_app.product_warning_template', {
    #                 'error': f"No mapping found for Product {product_id} with Serial {serial_number}.",
    #             })
    #
    #     # Complaint & reason codes
    #     complaint_types = request.env['complaint.type'].sudo().search([
    #         ('show_in_portal', '=', True)
    #     ])
    #     reason_codes = request.env['reason.code'].sudo().search([])
    #
    #     return request.render('customer_app.call_form_template', {
    #         'page_name': 'Create Ticket',
    #         'products': mappings,
    #         'complaint_types': complaint_types,
    #         'reason_codes': reason_codes,
    #         'default_product_id': default_mapping_id,
    #         'selected_serial': selected_serial,  # 🔹 Pass only matched serial
    #     })

    # # Controller code for submit ticket
    # @http.route('/ticket/submit', type='http', auth='user', website=True, csrf=True, methods=['POST'])
    # def call_submit(self, **post):
    #     call_name = post.get('name')
    #     problem_description = post.get('problem_description')
    #     priority = post.get('priority', '0')
    #     product_id = post.get('product_id')
    #     user = request.env.user
    #     partner = user.partner_id
    #
    #     complaint_type_ids_raw = request.httprequest.form.getlist('complaint_type_ids')
    #     complaint_type_ids = [int(cid) for cid in complaint_type_ids_raw if cid]
    #
    #     reason_code_ids = request.httprequest.form.getlist('reason_code_id')
    #     reason_code_ids = [int(x) for x in reason_code_ids if x]
    #
    #     date_deadline_str = post.get('date_deadline')
    #
    #     date_deadline = False
    #
    #     if date_deadline_str:
    #         try:
    #             # Parse local time string from browser
    #             local_dt = datetime.strptime(date_deadline_str.strip(), "%d/%m/%Y %H:%M:%S")
    #             local_tz = pytz.timezone('Asia/Kolkata')  # Change to your local timezone
    #             local_dt = local_tz.localize(local_dt)
    #
    #             # Convert to UTC and strip tzinfo to make it naive
    #             date_deadline = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
    #
    #             _logger.info("Parsed UTC-naive date_deadline: %s", date_deadline)
    #         except Exception as e:
    #             _logger.error("Date parsing failed: %s", e)
    #
    #     # Get or create the FSM project
    #     project = request.env['project.project'].sudo().search([('name', '=', 'Service Call')], limit=1)
    #     if not project:
    #         project = request.env['project.project'].sudo().create({
    #             'name': 'Service Call',
    #             'is_fsm': True,
    #         })
    #
    #     # Fetch all FSM stages from any FSM-enabled project
    #     fsm_stages = request.env['project.task.type'].sudo().search([
    #         ('project_ids.is_fsm', '=', True)
    #     ], order="sequence")
    #
    #     # Deduplicate by stage name
    #     unique_stages_by_name = OrderedDict()
    #     for stage in fsm_stages:
    #         if stage.name not in unique_stages_by_name:
    #             unique_stages_by_name[stage.name] = stage
    #
    #     stage_list = list(unique_stages_by_name.values())
    #     selected_stage = stage_list[0] if stage_list else False
    #
    #     if not selected_stage:
    #         return request.render('website.404')
    #
    #     partner_city_id = partner.city if partner.city else None
    #     department_id = None
    #
    #     if partner_city_id:
    #         # Step 2: Find matching department.service record with that city
    #         dept_service = request.env['department.service'].sudo().search([
    #             ('city_id', 'ilike', partner_city_id)
    #         ], limit=1)
    #
    #         # Step 3: If found, extract department_id
    #         if dept_service and dept_service.department_id:
    #             department_id = dept_service.department_id.id
    #
    #     planned_date_begin = datetime.now()
    #     # Create the FSM task
    #     task = request.env['project.task'].sudo().create({
    #         'name': call_name,
    #         'project_id': project.id,
    #         'is_fsm': True,
    #         'partner_id': partner.id,
    #         'problem_description': problem_description,
    #         'priority': priority,
    #         'date_deadline': date_deadline,
    #         'planned_date_begin': planned_date_begin,
    #         'customer_product_id': product_id,
    #         'complaint_type_id': [(6, 0, complaint_type_ids)],
    #         'reason_code_id': [(6, 0, reason_code_ids)],
    #         'user_ids': False,
    #         'stage_id': selected_stage.id,
    #         'department_id': department_id,
    #     })
    #
    #     # --- Check if today is company holiday ---
    #     today = datetime.now().date()
    #     company_id = user.company_id.id
    #
    #     holiday_today = request.env['resource.calendar.leaves'].sudo().search([
    #         ('company_id', '=', company_id),
    #         ('date_from', '<=', datetime.combine(today, datetime.max.time())),
    #         ('date_to', '>=', datetime.combine(today, datetime.min.time())),
    #     ], limit=1)
    #
    #     is_holiday = bool(holiday_today)
    #
    #     return request.render('customer_app.call_thank_you_template', {
    #         'page_name': 'Ticket',
    #         'is_holiday': is_holiday,
    #
    #     })

    @http.route('/ticket/submit', type='http', auth='user', website=True, csrf=True, methods=['POST'])
    def call_submit(self, **post):
        call_name = post.get('name')
        problem_description = post.get('problem_description')
        priority = post.get('priority', '0')
        mapping_id = int(post.get('product_id') or 0)  # here product_id is mapping.id
        user = request.env.user
        partner = user.partner_id

        complaint_type_ids_raw = request.httprequest.form.getlist('complaint_type_ids')
        complaint_type_ids = [int(cid) for cid in complaint_type_ids_raw if cid]

        reason_code_ids_raw = request.httprequest.form.getlist('reason_code_id')
        reason_code_ids = [int(x) for x in reason_code_ids_raw if x]

        # --- parse the service date ---
        service_date = post.get('date_deadline')
        planned_date_begin = False
        date_deadline = False
        if service_date:
            try:
                local_dt = datetime.strptime(service_date.strip(), "%d/%m/%Y %H:%M:%S")
                local_tz = pytz.timezone('Asia/Kolkata')
                local_dt = local_tz.localize(local_dt)
                # planned_date_begin is the selected date
                planned_date_begin = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                # date_deadline is 1 hour after planned_date_begin
                date_deadline = planned_date_begin + timedelta(hours=1)
                _logger.info("planned_date_begin (UTC-naive): %s, date_deadline: %s", planned_date_begin, date_deadline)
            except Exception as e:
                _logger.error("Date parsing failed: %s", e)

        # --- get or create FSM project ---
        project = request.env['project.project'].sudo().search([('name', '=', 'Service Call')], limit=1)
        if not project:
            project = request.env['project.project'].sudo().create({
                'name': 'Service Call',
                'is_fsm': True,
            })

        # --- FSM stage ---
        fsm_stages = request.env['project.task.type'].sudo().search(
            [('project_ids.is_fsm', '=', True)], order="sequence")
        unique_stages_by_name = OrderedDict()
        for stage in fsm_stages:
            if stage.name not in unique_stages_by_name:
                unique_stages_by_name[stage.name] = stage
        stage_list = list(unique_stages_by_name.values())
        selected_stage = stage_list[0] if stage_list else False
        if not selected_stage:
            return request.render('website.404')

        # --- department & assignee from customer's city ---
        partner_city_id = partner.city_id.name if hasattr(partner, 'city_id') and partner.city_id else partner.city
        partner_state = partner.state_id.name if partner.state_id else False

        dept_service = False
        department_id = None
        assigned_users = []

        if partner_city_id:
            dept_service = request.env['department.service'].sudo().search(
                [('city_id.name', 'ilike', partner_city_id)], limit=1)

        else:
            # No city_id → match by state
            if partner_state:
                dept_service = request.env['department.service'].sudo().search([
                    ('state_id.name', 'ilike', partner_state)
                ], limit=1)

        if dept_service and dept_service.department_id:
            department_id = dept_service.department_id.id

            # --- department's supervisor from city ---
            assigned_user = None

            # Find users in that department
            department_users = request.env['res.users'].sudo().search([
                ('employee_ids.department_id', '=', department_id)
            ])

            # Try FSM Supervisors first (not Managers)
            supervisors = department_users.filtered(
                lambda u: u.has_group('industry_fsm.group_fsm_supervisor')
                          and not u.has_group('industry_fsm.group_fsm_manager')
            )

            if supervisors:
                assigned_user = supervisors[0]
            else:
                # Fallback: FSM Manager in that department
                managers = department_users.filtered(
                    lambda u: u.has_group('industry_fsm.group_fsm_manager')
                )
                if managers:
                    assigned_user = managers[0]

            if assigned_user:
                assigned_users = [assigned_user.id] or []

        # --- get mapping record and its serial number ---
        # serial_number_id = False
        # if mapping_id:
        #     mapping = request.env['customer.product.mapping'].sudo().browse(mapping_id)
        #     if mapping and mapping.serial_number_ids:
        #         # take the first serial number if there are several
        #         serial_number_id = mapping.serial_number_ids[0].id

        # --- Mapping record and serial number ---
        serial_number_id = False
        unit_status_value = False
        call_type_value = False
        if mapping_id:
            mapping = request.env['customer.product.mapping'].sudo().browse(mapping_id)
            if mapping:
                # Take first serial number if available
                if mapping.serial_number_ids:
                    serial_number_id = mapping.serial_number_ids[0].id

                # Set unit_status from mapping.status
                if mapping.status:
                    unit_status_value = mapping.status  # If unit_status is Selection
                    # Auto set call_type based on mapping.status
                    call_type_record = request.env['call.type'].sudo().search(
                        [('name', 'ilike', mapping.status.strip())], limit=1)
                    if call_type_record:
                        call_type_value = call_type_record.id
                        print("Auto-set call_type ID: %s, Name: %s", call_type_value, call_type_record.name)

        # --- create the FSM task ---
        task_vals = {
            'name': call_name,
            'project_id': project.id,
            'is_fsm': True,
            'partner_id': partner.id,
            'problem_description': problem_description,
            'priority': priority,
            'date_deadline': date_deadline,
            'planned_date_begin': planned_date_begin,
            'customer_product_id': mapping_id,  # mapping.id
            'complaint_type_id': [(6, 0, complaint_type_ids)],
            'reason_code_id': [(6, 0, reason_code_ids)],
            'stage_id': selected_stage.id,
            # 'department_id': department_id,
            # 'user_ids': False,
            'department_id': department_id,
            'user_ids': [(6, 0, assigned_users)],
            'call_type': call_type_value,

        }

        # add serial number to the task if found
        if serial_number_id:
            task_vals['serial_number'] = serial_number_id

        task = request.env['project.task'].sudo().create(task_vals)

        # --- check holiday ---
        today = datetime.now().date()
        company_id = user.company_id.id
        holiday_today = request.env['resource.calendar.leaves'].sudo().search([
            ('company_id', '=', company_id),
            ('date_from', '<=', datetime.combine(today, datetime.max.time())),
            ('date_to', '>=', datetime.combine(today, datetime.min.time())),
        ], limit=1)
        is_holiday = bool(holiday_today)

        return request.render('customer_app.call_thank_you_template', {
            'page_name': 'Ticket',
            'is_holiday': is_holiday,
        })

    @http.route('/my/ticket/reschedule/<int:ticket_id>', type='http', auth='user', website=True)
    def ticket_reschedule_form(self, ticket_id, **kw):
        # Check if model exists
        if 'project.task' not in request.env:
            return request.render('website.404')

        ticket = request.env['project.task'].sudo().browse(ticket_id)
        if not ticket.exists():
            return request.render('website.404')

        return request.render('customer_app.reschedule_form_template', {
            'ticket': ticket,
            'page_name': 'Reschedule Ticket'
        })

    @http.route('/my/ticket/reschedule/submit', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def ticket_reschedule_submit(self, **post):
        if 'project.task' not in request.env:
            return request.render('website.404')

        ticket_id = int(post.get('ticket_id', 0))
        new_name = post.get('name')
        date_deadline_str = post.get('date_deadline')

        date_deadline = False
        if date_deadline_str:
            try:
                date_deadline = datetime.strptime(date_deadline_str, "%Y-%m-%d").date()
            except Exception as e:
                _logger.error("Date parsing failed: %s", e)

        ticket = request.env['project.task'].sudo().browse(ticket_id)
        if ticket.exists():
            ticket.write({
                'name': new_name,
                'date_deadline': date_deadline,
            })

        return request.redirect(f'/my/ticket/{ticket.id}')

    @http.route('/my/ticket/<int:ticket_id>/cancel', type='http', auth='user', website=True, methods=['POST'],
                csrf=True)
    def ticket_cancel(self, ticket_id, **post):
        if 'project.task' not in request.env or 'project.task.type' not in request.env:
            return request.render('website.404')

        ticket = request.env['project.task'].sudo().browse(ticket_id)
        if not ticket.exists():
            return request.render('website.404')

        # Safe cancel stage lookup
        try:
            if ticket.stage_id and ticket.stage_id.name in ['New', 'Assigned', 'Planned']:
                cancel_stage = request.env['project.task.type'].sudo().search([
                    ('name', 'ilike', 'cancel'),
                    ('project_ids', 'in', ticket.project_id.id)
                ], limit=1)
                if cancel_stage:
                    ticket.write({'stage_id': cancel_stage.id})
                else:
                    _logger.warning("Canceled stage not found for project %s", ticket.project_id.name)
        except Exception as e:
            _logger.error("Error in cancelling ticket: %s", e)

        return request.redirect(f'/my/ticket/{ticket.id}')

    @http.route('/my/ticket/<int:ticket_id>/feedback', type='json', auth='user', methods=['POST'], csrf=True)
    def submit_feedback(self, ticket_id):
        try:
            # Check if project.task model exists
            if 'project.task' not in request.env:
                return Response(
                    json.dumps({'success': False, 'error': 'Task model not available'}),
                    content_type='application/json;charset=utf-8'
                )

            # Get request data
            data = request.httprequest.get_json(force=True, silent=True)
            if not data:
                return Response(
                    json.dumps({'success': False, 'error': 'Invalid JSON'}),
                    content_type='application/json;charset=utf-8'
                )

            rating = int(data.get('rating', 0))
            message = data.get('message', '')

            task = request.env['project.task'].sudo().browse(ticket_id)
            if not task.exists():
                return Response(
                    json.dumps({'success': False, 'error': 'Ticket not found'}),
                    content_type='application/json;charset=utf-8'
                )

            # Use getattr to avoid crash if field is missing (e.g., if industry_fsm is uninstalled)
            sequence = getattr(task, 'sequence_fsm', task.name)
            stars = '⭐' * rating + '☆' * (5 - rating)
            feedback_text = (
                f"Ticket Number: {sequence}\n"
                f"Call Name: {task.name}\n"
                f"Customer: {task.partner_id.name or 'N/A'}\n"
                f"Rating: {stars} ({rating}/5)\n"
                f"Feedback: {message}"
            )

            _logger.info("Feedback Received:\n%s", feedback_text)

            # Notify users based on feedback rating
            notif_rules = request.env['feedback.notification'].sudo().search([], order='feedback_status desc')
            threshold_map = {'below_5': 5, 'below_4': 4, 'below_3': 3}

            matched_rules = notif_rules.filtered(
                lambda r: rating <= threshold_map.get(r.feedback_status, 5)
            )

            # Get rule users and task assignees
            rule_users = matched_rules.mapped('user_ids')
            assignee_users = task.user_ids
            users_to_notify = rule_users & assignee_users

            notified_users = set()
            for user in users_to_notify:
                if user.id in notified_users:
                    continue
                user.partner_id.sudo().message_post(
                    subject="Low Customer Feedback",
                    body=feedback_text,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                    partner_ids=[user.partner_id.id],
                )
                notified_users.add(user.id)

            return Response(
                json.dumps({'success': True}),
                content_type='application/json;charset=utf-8'
            )

        except Exception as e:
            _logger.exception("Feedback submission failed")
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                content_type='application/json;charset=utf-8'
            )

    @http.route(['/my/contract/list'], type='http', auth='user', website=True)
    def contract_list(self, sortby='name', filterby='all', groupby='', search='', **kwargs):

        today = date.today()
        next_30_days = today + relativedelta(days=30)

        registry = request.env.registry
        if 'amc.contract' not in registry:
            return request.render("website.404")

        user = request.env.user
        partner = user.partner_id

        # --- Domain base ---
        domain = [('partner_id', '=', partner.id)]

        # --- Search ---
        if search:
            domain += ['|', '|', '|', '|',
                       ('name', 'ilike', search),
                       ('contract_type.name', 'ilike', search),
                       ('start_date', 'ilike', search),
                       ('end_date', 'ilike', search),
                       ('stage_id', 'ilike', search),
                       ]

        contracts = request.env['amc.contract'].sudo().search(domain)

        # --- Sortings ---
        sortings = {
            'name': {'label': 'Name', 'order': 'name'},
            'recent': {'label': 'Newest', 'order': 'create_date desc'},
        }
        sort_key = sortings.get(sortby, sortings['name'])['order']
        contracts = contracts.sorted(
            key=lambda c: getattr(c, sort_key.split()[0], '') or '',
            reverse='desc' in sort_key
        )

        # --- Filters ---
        filters = {
            'all': {'label': 'All', 'domain': []},
            'expiring_30': {
                'label': 'Expiring in 30 Days',
                'domain': lambda c: c.end_date and today <= c.end_date <= next_30_days
            }
        }

        # Apply filters
        filter_func = filters.get(filterby, filters['all']).get('domain')
        if callable(filter_func):
            contracts = list(filter(filter_func, contracts))

        # Grouping
        grouped_contracts = {}
        if groupby == 'type':
            for contract in contracts:
                key = contract.contract_type.name or 'No Type'
                grouped_contracts.setdefault(key, []).append(contract)
        elif groupby == 'stage':
            for contract in contracts:
                key = contract.stage_id or 'No Stage'
                grouped_contracts.setdefault(str(key), []).append(contract)

        # Unified Dropdown Options
        combined_options = {}
        # First filters
        for key, value in filters.items():
            combined_options[f'f_{key}'] = {'label': f"{value['label']}", 'filterby': key, 'groupby': groupby}
        # Then group by options
        for key, value in {
            'type': {'label': 'Contract Type'},
            'stage': {'label': 'Stage'}
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"Group By: {value['label']}",
                'groupby': key
            }

        return request.render('customer_app.contract_list_view', {
            'page_name': 'My Contracts',
            'contracts': contracts,
            'grouped_contracts': grouped_contracts,
            'search': search,
            'filterby': filterby,
            'groupby': groupby,
            'search_in': 'name',
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_combined': combined_options,
            'default_url': '/my/contract/list',
            'format_date': lambda date: format_date(request.env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'stage_selection': dict(request.env['amc.contract']._fields.get('stage_id', fields.Selection()).selection)
            if 'amc.contract' in request.env else {},
        })

    @http.route(['/my/contract/form/<int:contract_id>'], type='http', auth='user', website=True)
    def view_contract_form(self, contract_id, **kw):

        registry = request.env.registry
        if 'amc.contract' not in registry:
            return request.render("website.404")

        user = request.env.user
        partner = user.partner_id
        amc_contract = request.env['amc.contract'].sudo()
        contract = amc_contract.browse(contract_id)

        if not contract.exists() or contract.partner_id.id != partner.id:
            return request.render("website.403")

        domain = [
            ('is_amc', '=', True),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['sent', 'sale']),
            ('amc_contract_id', '=', contract.id)
        ]
        sale_order = request.env['sale.order'].sudo().search(domain, order="date_order desc")

        contract_id_list = request.session.get('my_contract_list') or []
        if contract.id not in contract_id_list:
            contract_id_list = amc_contract.search([
                ('partner_id', '=', partner.id)
            ], order="create_date desc").ids
            request.session['my_contract_list'] = contract_id_list

        prev_contract_id = next_contract_id = None
        if contract.id in contract_id_list:
            index = contract_id_list.index(contract.id)
            if index > 0:
                prev_contract_id = contract_id_list[index - 1]
            if index < len(contract_id_list) - 1:
                next_contract_id = contract_id_list[index + 1]

        # Safe asset count
        asset_count = 0
        if 'amc.contract.asset.line' in request.env and contract.stage_id == 'active':
            asset_count = request.env['amc.contract.asset.line'].sudo().search_count([
                ('contract_id', '=', contract.id)
            ])

        # Sale order count
        sale_order_count = request.env['sale.order'].sudo().search_count([
            ('amc_contract_id', '=', contract.id),
            ('is_amc', '=', True),
            ('partner_id', '=', request.env.user.partner_id.id)
        ])

        # Invoices
        invoice_domain = [
            ('amc_contract_id', '=', contract.id),
            ('partner_id', '=', partner.id)
        ]
        invoices = request.env['account.move'].sudo().search(invoice_domain, order="invoice_date desc")

        next_renewal = ''
        today = datetime.today().date()
        if contract.end_date:
            days_left = (contract.end_date - today).days
            formatted_end_date = format_date(request.env, contract.end_date, date_format='dd/MM/yyyy')
            if 0 <= days_left <= 30:
                next_renewal = f"Going out of Coverage Soon: {formatted_end_date} (in {days_left} day{'s' if days_left != 1 else ''})"

        return request.render("customer_app.contract_form_view", {
            'contract': contract,
            'page_name': 'Contract',
            'asset_count': asset_count,
            'sale_order_count': sale_order_count,
            'sale_orders': sale_order,
            'invoices': invoices,
            'next_renewal': next_renewal,
            'prev_record': f'/my/contract/form/{prev_contract_id}' if prev_contract_id else None,
            'next_record': f'/my/contract/form/{next_contract_id}' if next_contract_id else None,
            'format_date': lambda date: format_date(request.env, date, date_format='dd/MM/yyyy') if date else 'N/A',
        })

    @http.route(['/my/invoice/<int:invoice_id>'], type='http', auth='user', website=True)
    def portal_invoice_detail(self, invoice_id, **kw):
        user = request.env.user
        partner = user.partner_id
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if not invoice.exists() or invoice.partner_id.id != partner.id:
            return request.render("website.403")
        return request.render("customer_app.amc_invoice_template", {
            'invoice': invoice,
            'object': invoice,  # Needed by portal.message_thread
            'token': invoice.access_token,
            'pid': partner.id,
            'report_type': 'html',
            'portal_confirmation': request.params.get('portal_confirmation'),
            'success': request.params.get('success'),
            'error': request.params.get('error'),
            'is_html_empty': lambda html: not html or not html.strip(),
        })

    # @http.route(['/my/invoices/<int:invoice_id>/pay'], type='http', auth="user", website=True)
    # def portal_invoice_pay(self, invoice_id, **kw):
    #     invoice = request.env['account.move'].sudo().browse(invoice_id).exists()
    #     if not invoice or invoice.move_type != 'out_invoice':
    #         return request.not_found()
    #
    #     # Redirect to Odoo's standard payment flow
    #     return request.redirect('/my/invoices/%s' % invoice_id + '?access_token=%s' % invoice.access_token)

    @http.route(['/my/notifications'], type='http', auth='user', website=True)
    def portal_notifications(self, filterby='unread', groupby='', search='', **kwargs):
        partner = request.env.user.partner_id

        # --- Base domain ---
        domain = [('partner_id', '=', partner.id)]

        # --- Search ---
        if search:
            domain += ['|', '|',
                       ('title', 'ilike', search),
                       ('message', 'ilike', search),
                       ('create_date', 'ilike', search),
                       ]

        # --- Filters ---
        filters = {
            'all': {'label': 'All', 'domain': []},
            'read': {'label': 'Read', 'domain': [('is_read', '=', True)]},
            'unread': {'label': 'Unread', 'domain': [('is_read', '=', False)]},
        }

        # --- Group By Options ---
        groupbys = {
            '': {'label': 'No Group'},
            'title': {'label': 'Title'},
        }

        # --- Apply Filter ---
        domain += filters.get(filterby, filters['all'])['domain']

        # --- Fetch records ---
        notifications = request.env['portal.notification'].sudo().search(domain, order='create_date desc')

        # --- Apply GroupBy ---
        grouped_notifications = {}
        if groupby == 'title':
            for note in notifications:
                key = note.title or 'No Title'
                grouped_notifications.setdefault(key, []).append(note)
        else:
            grouped_notifications = None

        # --- Unified Dropdown Options (Filters + GroupBy) ---

        combined_options = {}

        # First filters
        for key, value in filters.items():
            combined_options[f'f_{key}'] = {  # prefix with f_
                'label': value['label'],
                'filterby': key,
                'groupby': groupby
            }

        # Then group by options
        for key, value in groupbys.items():
            if key:  # skip empty key
                combined_options[f'g_{key}'] = {  # prefix with g_
                    'label': f"{value['label']}",
                    'filterby': filterby,
                    'groupby': key
                }

        return request.render("customer_app.portal_my_notifications", {
            'page_name': 'notifications',
            'notifications': notifications,
            'grouped_notifications': grouped_notifications,
            'filterby': filterby,
            'groupby': groupby,
            'search': search,
            'searchbar_combined': combined_options,
            'default_url': '/my/notifications',
            'format_datetime': format_datetime,
        })

    @http.route(['/my/notifications/read/<int:note_id>'], type='http', auth='user', website=True)
    def portal_mark_notification_read(self, note_id, **kw):
        notification = request.env['portal.notification'].sudo().browse(note_id)
        user = request.env.user
        if notification and notification.partner_id == user.partner_id:
            notification.write({'is_read': True})
            return request.redirect(notification.url or '/my/notifications')
        return request.redirect('/my/notifications')

    @http.route(['/my/notifications/read_all'], type='http', auth='user', website=True)
    def portal_mark_all_notifications_read(self, **kw):
        partner = request.env.user.partner_id
        request.env['portal.notification'].sudo().search([
            ('partner_id', '=', partner.id),
            ('is_read', '=', False)
        ]).write({'is_read': True})

        return request.redirect('/my/notifications')


class QuotationPortal(CustomerPortal):
    @http.route('/my/quotation/orders/<int:order_id>', type='http', auth='user', website=True)
    def view_amc_quotation_form(self, order_id, **kwargs):
        user = request.env.user
        partner = user.partner_id

        order_sudo = request.env['sale.order'].sudo().browse(order_id)
        if not order_sudo.exists() or order_sudo.partner_id.id != partner.id:
            return request.render("website.403")

        # Copy Odoo logic: Set access token
        token = order_sudo._portal_ensure_token()

        # Include Payment Context if order requires payment
        values = {
            'sale_order': order_sudo,
            'object': order_sudo,  # Required by message thread
            'token': token,
            'pid': partner.id,
            'report_type': 'html',
            'portal_confirmation': request.params.get('portal_confirmation'),
            'success': request.params.get('success'),
            'error': request.params.get('error'),
            'product_documents': order_sudo.order_line.mapped('product_id.product_document_ids'),
            'is_html_empty': lambda html: not html or not html.strip(),
        }

        # Include payment values ONLY if payment is required
        if order_sudo._has_to_be_paid():
            downpayment = kwargs.get('downpayment', False)
            downpayment = downpayment == 'true' if downpayment is not None else order_sudo.prepayment_percent < 1.0
            values.update(
                self._get_payment_values(order_sudo, downpayment=downpayment)
            )

        return request.render("customer_app.amc_quotation_template", values)


class TicketPaymentPortal(payment_portal.PaymentPortal):

    def _get_ticket_payment_values(self, ticket_sudo, **kwargs):
        """Return payment context values for the ticket portal payment modal."""
        partner = request.env.user.partner_id
        amount = ticket_sudo.remaining_amount
        currency = ticket_sudo.company_id.currency_id
        company = ticket_sudo.company_id

        # 1. Fetch providers
        providers_sudo = request.env['payment.provider'].sudo().search([
            ('company_id', '=', company.id),
            ('state', '=', 'test')
        ])

        # 2. Fetch payment methods
        payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
            providers_sudo.ids, partner.id, currency_id=currency.id, **kwargs
        )

        # 3. Fetch tokens
        tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
            providers_sudo.ids, partner.id, **kwargs
        )

        # 4. Compute show_tokenize_input_mapping (needed by payment.method_form)
        show_tokenize_input_mapping = payment_portal.PaymentPortal._compute_show_tokenize_input_mapping(
            providers_sudo, ticket_id=ticket_sudo.id
        )

        # Debug logs
        if providers_sudo:
            print("Providers:", [p.name for p in providers_sudo])
        else:
            print("No providers found")

        if payment_methods_sudo:
            print("Payment Methods:", [m.name for m in payment_methods_sudo])
        else:
            print("No payment methods found")

        if tokens_sudo:
            print("Tokens:", [t.id for t in tokens_sudo])
        else:
            print("No tokens found")

        return {
            'amount': amount,
            'currency': currency,
            'partner_id': partner.id,
            'providers_sudo': providers_sudo,
            'payment_methods_sudo': payment_methods_sudo,
            'tokens_sudo': tokens_sudo,
            'transaction_route': f"/my/ticket/{ticket_sudo.id}/transaction",
            'landing_route': f"/my/ticket/{ticket_sudo.id}",
            'access_token': ticket_sudo.access_token,
            'company_mismatch': False,
            'expected_company': company,  # used in some templates
            'show_tokenize_input_mapping': show_tokenize_input_mapping,
        }

    @http.route('/my/ticket/<int:ticket_id>/transaction', type='json', auth='user', website=True)
    def portal_ticket_transaction(self, ticket_id, **kwargs):
        ticket_sudo = request.env['project.task'].sudo().browse(ticket_id).exists()
        if not ticket_sudo:
            raise ValidationError(_("Ticket not found"))

        partner = request.env.user.partner_id

        try:
            payment_amount = float(kwargs.get('amount', ticket_sudo.remaining_amount))
        except (TypeError, ValueError):
            payment_amount = ticket_sudo.remaining_amount

        if payment_amount <= 0 or payment_amount > ticket_sudo.remaining_amount:
            payment_amount = ticket_sudo.remaining_amount

        currency = ticket_sudo.company_id.currency_id

        kwargs.update({
            'partner_id': partner.id,
            'currency_id': currency.id,
            'amount': payment_amount,
        })

        # Create payment transaction (from Odoo standard method)
        tx_sudo = self._create_transaction(
            custom_create_values={'ticket_id': ticket_sudo.id},
            **kwargs
        )

        # Update ticket amounts
        new_remaining = ticket_sudo.remaining_amount - payment_amount
        ticket_sudo.sudo().write({
            'remaining_amount': new_remaining,
            'paid_amount': ticket_sudo.paid_amount + payment_amount,
            'payment_status': 'paid' if new_remaining <= 0 else 'partial',
        })

        #  Automatically register payment and create journal
        journal = request.env['account.journal'].sudo().search([('name', '=', 'Service Call')], limit=1)
        if not journal:
            raise ValidationError(_("Journal 'Service Call' not found"))

        payment_method_line = request.env['account.payment.method.line'].sudo().search([
            ('journal_id', '=', journal.id)
        ], limit=1)
        if not payment_method_line:
            raise ValidationError(_("No payment method line found for journal '%s'" % journal.name))

        # Create account.payment record
        payment_vals = {
            'partner_id': partner.id,
            'amount': payment_amount,
            'payment_type': 'inbound',
            'journal_id': journal.id,
            'payment_method_line_id': payment_method_line.id,
            'task_id': ticket_sudo.id,
            'currency_id': currency.id,
            'ref': f'Payment by {partner.name} - {ticket_sudo.sequence_fsm}',
        }

        payment = request.env['account.payment'].sudo().create(payment_vals)
        payment.action_post()

        # Link journal entry to task (if needed)
        if payment.move_id:
            ticket_sudo.sudo().write({
                'journal_entry_id': payment.move_id.id,
            })

        # create wizard record (history metadata)
        request.env['service.call.payment.wizard'].sudo().create({
            'task_id': ticket_sudo.id,
            'amount': payment_amount,
            'ref': f'Auto portal payment by {partner.name}',
            'payment_method_line_id': payment_method_line.id,
            'journal_id': journal.id,
        })

        return tx_sudo._get_processing_values()

    @http.route(['/my/quotations/<int:order_id>'], type='http', auth="user", website=True)
    def portal_custom_order_page(self, order_id, access_token=None, **kw):
        # Reuse logic from existing method to fetch sale order and render
        response = super().portal_order_page(
            order_id=order_id,
            access_token=access_token,
            **kw
        )
        return response

# class WebPushController(http.Controller):
#
#     @http.route('/webpush/get_vapid_key', type='json', auth='public')
#     def get_vapid_key(self):
#         vapid_key = request.env['ir.config_parameter'].sudo().get_param('mail.web_push_vapid_public_key')
#         return {"vapid_public_key": vapid_key}
#     # def get_vapid_key(self):
#     #     # Assuming it's stored in ir.config_parameter (common in Odoo webpush modules)
#     #     vapid_key = request.env['ir.config_parameter'].sudo().get_param('webpush.vapid_public_key')
#     #     return {"vapid_public_key": vapid_key}
#
#
#     @http.route('/webpush/subscribe', type='json', auth='user')
#     def subscribe(self, **kwargs):
#         user = request.env.user
#         subscription = kwargs
#         if subscription:
#             user.sudo().write({
#                 "webpush_subscription": subscription  # you need a JSON field on res.users
#             })
#         return {"status": "ok"}

#
# class PortalAccount(http.Controller):
#
#     @http.route(['/my/invoices'], type='http', auth="user", website=True)
#     def portal_my_invoices(self, **kwargs):
#         invoices = request.env['account.move'].sudo().search([
#             ('partner_id', '=', request.env.user.partner_id.id),
#             ('move_type', '=', 'out_invoice'),
#             ('state', 'in', ['posted'])
#         ])
#         invoices_data = []
#         for inv in invoices:
#             invoices_data.append({
#                 'id': inv.id,
#                 'name': inv.name,
#                 'amount_total': inv.amount_total,
#                 'amount_residual': inv.amount_residual,  # include this
#                 'payment_state': inv.payment_state,
#                 'currency_id': inv.currency_id.id,
#             })
#         return request.render("account.portal_my_invoices", {
#             'invoices': invoices_data
#         })
