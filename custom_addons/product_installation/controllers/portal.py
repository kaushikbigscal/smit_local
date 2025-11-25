# In your custom addon: controllers/portal.py
from odoo import fields, http, _
from odoo.http import request
from datetime import date
from collections import OrderedDict
from odoo.tools import format_date
from odoo.addons.customer_app.controllers.portal import PortalHomePage


class InstallationTicketPortal(PortalHomePage):

    @http.route(['/my/home', '/my'], type='http', auth="user", website=True)
    def portal_my_home(self, **kwargs):
        # Get the original response
        response = super().portal_my_home(**kwargs)

        if hasattr(response, 'qcontext'):
            values = response.qcontext.copy()
        else:
            values = self._get_portal_values(**kwargs)

        user = request.env.user
        partner = user.partner_id

        Task = request.env['project.task'].sudo()
        if 'project.task' in request.env and hasattr(Task, 'is_fsm'):
            total_installation_tickets = Task.search_count([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True),
                ('name', 'ilike', 'installation'),
            ])

            pending_installation_tickets = Task.search_count([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True),
                ('name', 'ilike', 'installation'),
                ('installation_request_confirmed', '=', False),
            ])
        else:
            total_installation_tickets = 0
            pending_installation_tickets = 0

        values.update({
            'installation_ticket_count': total_installation_tickets,
            'installation_ticket_pending': pending_installation_tickets,
            'fsm_installed': True,
        })

        return request.render("portal.portal_my_home", values)

    def _get_portal_values(self, **kwargs):
        """Helper method to recreate portal values if needed"""
        user = request.env.user
        partner = user.partner_id
        today = date.today()

        # Get FSM installation check
        fsm_installed = 'project.task' in request.env and 'is_fsm' in request.env['project.task']._fields

        # Basic counts
        quotation_count = request.env['sale.order'].search_count([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sent'),
        ])

        quotation = request.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sent'),
        ], order='create_date desc', limit=2)

        # Asset counts
        active_asset_count = 0
        under_service_count = 0
        operational_count = 0
        asset_status_message = "No assets"

        if 'customer.product.mapping' in request.env:
            domain_asset = [
                ('customer_id', '=', partner.id),
                '|', ('start_date', '=', False), ('start_date', '<=', today),
                '|', ('end_date', '=', False), ('end_date', '>=', today)
            ]
            active_assets = request.env['customer.product.mapping'].sudo().search(domain_asset)
            active_asset_count = len(active_assets)

            if active_asset_count > 0:
                done_stages = request.env['project.task.type'].sudo().search([
                    ('name', 'in', ['Done', 'Cancelled', 'Resolved'])
                ])
                under_service_ids = request.env['project.task'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('customer_product_id', 'in', active_assets.ids),
                    ('stage_id', 'not in', done_stages.ids),
                ]).mapped('customer_product_id.id')

                under_service_count = len(set(under_service_ids))
                assets_with_tickets = request.env['project.task'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('customer_product_id', 'in', active_assets.ids),
                    ('stage_id', 'not in', done_stages.ids),
                ]).mapped('customer_product_id.id')
                operational_count = active_asset_count - len(set(assets_with_tickets))

                if under_service_count == 0:
                    asset_status_message = "All Operational"
                else:
                    asset_status_message = f"{under_service_count} under service, {operational_count} operational"

        # Contract data
        contract_count = 0
        my_contract = []
        is_expired = False
        contract_renewal_message = "No contracts found"

        if 'amc.contract' in request.env:
            my_contract = request.env['amc.contract'].sudo().search([
                ('partner_id', '=', partner.id),
            ], order="create_date desc", limit=2)
            contract_count = request.env['amc.contract'].sudo().search_count([
                ('partner_id', '=', partner.id),
            ])

        # Other data
        assigned_calls = []
        if fsm_installed:
            assigned_calls = request.env['project.task'].sudo().search([
                ('partner_id', '=', partner.id),
                ('is_fsm', '=', True)
            ], order="create_date desc", limit=2)

        mappings = []
        if 'customer.product.mapping' in request.env:
            mappings = request.env['customer.product.mapping'].sudo().search([
                ('customer_id', '=', partner.id)
            ], order='create_date desc', limit=2)

        return {
            'fsm_installed': fsm_installed,
            'quotation': quotation,
            'quotation_count': quotation_count,
            'active_asset_count': active_asset_count,
            'under_service_count': under_service_count,
            'operational_count': operational_count,
            'asset_status_message': asset_status_message,
            'assigned_calls': assigned_calls,
            'mappings': mappings,
            'my_contract': my_contract,
            'contract_count': contract_count,
            'is_expired': is_expired,
            'contract_renewal_message': contract_renewal_message,
            'company': request.env.company,
        }

    @http.route(['/my/installation/tickets'], type='http', auth='user', website=True)
    def list_installation_tickets(self, sortby='recent', filterby='all', groupby='', search='', **kwargs):
        env = request.env
        user = env.user
        partner = user.partner_id

        # Check if FSM is installed
        if 'project.task' not in env or 'is_fsm' not in env['project.task']._fields:
            return request.render('product_installation.installation_ticket_list_view', {
                'calls': [],
                'installation_tickets': [],
                'page_name': 'Installation Tickets',
                'grouped_calls': {},
                'search': search,
                'filterby': filterby,
                'groupby': groupby,
                'search_in': 'name',
                'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
                'searchbar_filters': {},
                'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
                'searchbar_groupby': {},
                'default_url': '/my/installation/tickets',
            })

        Task = env['project.task'].sudo()
        excluded_names = ['Done', 'Cancelled', 'Resolved']

        domain = [
            ('partner_id', '=', partner.id),
            ('is_fsm', '=', True),
            ('name', 'ilike', 'installation')
        ]

        # Search functionality
        if search:
            search_domain = ['|', '|', '|', '|', '|', '|',
                             ('name', 'ilike', search),
                             ('sequence_fsm', 'ilike', search),
                             ('customer_product_id.product_id.name', 'ilike', search),
                             ('user_ids.name', 'ilike', search),
                             ('create_date', 'ilike', search),
                             ('planned_date_begin', 'ilike', search),
                             ('stage_id.name', 'ilike', search)]
            domain += search_domain

        calls = Task.search(domain)

        # Sorting
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

        # Filters
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

        # Grouping
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

        # Combined options for frontend dropdown
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

        installation_tickets = Task.search([
            ('partner_id', '=', partner.id),
            ('is_fsm', '=', True),
            ('name', 'ilike', 'installation')
        ]).filtered(
            lambda t: t.stage_id and t.stage_id.name not in excluded_names
        )

        return request.render('product_installation.installation_ticket_list_view', {
            'calls': calls,
            'installation_tickets': installation_tickets,
            'page_name': 'Installation Tickets',
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
            'default_url': '/my/installation/tickets',
            'format_date': lambda date: format_date(env, date, date_format='dd/MM/yyyy') if date else 'N/A',
            'installation_ticket_count': len(installation_tickets),
        })


    @http.route('/my/ticket/<int:task_id>/installation_request', type='http', auth='user', website=True,
                methods=['POST'])
    def installation_request(self, task_id, **post):
        task = request.env['project.task'].sudo().browse(task_id)
        if task and task.project_id.name == 'Service Call' and task.is_fsm:
            assignee_partners = task.user_ids.mapped('partner_id')
            print("assignee partners:", assignee_partners)
            task.message_post(
                body="Installation Request Confirmed by Customer. You Are ready for service",
                partner_ids=[p.id for p in assignee_partners],
                message_type="comment",
                subtype_xmlid='mail.mt_note'
            )

        return request.redirect(f'/my/ticket/{task_id}')

    
