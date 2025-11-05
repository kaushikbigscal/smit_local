from odoo import http
from odoo.http import request
from odoo.addons.customer_app.controllers.portal import PortalHomePage
from odoo.tools import format_date
from odoo import _
from ..utils import is_fsm_installed


class PortalHomeWithPartsRequest(PortalHomePage):

    @http.route(['/my/home', '/my'], type='http', auth="user", website=True)
    def portal_my_home(self, **kwargs):
        response = super().portal_my_home(**kwargs)

        if hasattr(response, 'qcontext'):
            values = response.qcontext
        else:
            values = {}

        partner = request.env.user.partner_id
        parts_request_count = 0
        parts_request_pending_count = 0

        if 'part.customer.approval.notification' in request.env.registry.models:
            all_records = request.env['part.customer.approval.notification'].sudo().search([
                ('task_id.partner_id', '=', partner.id),
                ('coverage', '=', 'chargeable')
            ])
            parts_request_count = len(all_records)

            pending_records = request.env['part.customer.approval.notification'].sudo().search([
                ('task_id.partner_id', '=', partner.id),
                ('coverage', '=', 'chargeable'),
                ('stage', '=', 'pending')
            ])
            parts_request_pending_count = len(pending_records)

        values['parts_request_count'] = parts_request_count
        values['parts_request_pending_count'] = parts_request_pending_count

        return request.render("portal.portal_my_home", values)

    @http.route('/my/parts/request', type='http', auth="user", website=True)
    def portal_my_parts_request(self, sortby='newest', filterby='all', groupby='', search='', **kwargs):
        """Parts Request List View with sorting, filtering and grouping"""
        user = request.env.user
        partner = user.partner_id

        # Base domain
        domain = [('task_id.partner_id', '=', partner.id),
                  ('coverage', '=', 'chargeable')]

        # Search functionality
        if search:
            search_domain = ['|', '|', '|', '|',
                             ('part_name', 'ilike', search),
                             ('product_id.name', 'ilike', search),
                             ('task_id.user_ids.name', 'ilike', search),
                             ('stage', 'ilike', search)]
            domain += search_domain

        # Sorting options
        sortings = {
            'newest': {'label': 'Newest First', 'order': 'create_date desc, id desc'},
            'oldest': {'label': 'Oldest First', 'order': 'create_date asc, id asc'},
            'product': {'label': 'Product Name', 'order': 'product_id'},
            'stage': {'label': 'Stage', 'order': 'stage'},
        }
        order = sortings.get(sortby, sortings['newest'])['order']

        # Filtering options
        filters = {
            'all': {'label': 'All', 'domain': []},
            'pending': {'label': 'Pending', 'domain': [('stage', '=', 'pending')]},
            'approved': {'label': 'Approved', 'domain': [('stage', '=', 'approved')]},
            'rejected': {'label': 'Rejected', 'domain': [('stage', '=', 'rejected')]},
        }

        # Apply filter
        filter_domain = filters.get(filterby, filters['all'])['domain']
        if filter_domain:
            domain += filter_domain

        parts_requests = []
        if 'part.customer.approval.notification' in request.env.registry.models:
            parts_requests = request.env['part.customer.approval.notification'].sudo().search(
                domain,
                order=order
            )

        # --- Grouping ---
        grouped_requests = {}
        if groupby and groupby != 'none':
            if groupby == 'stage':
                for req in parts_requests:
                    stage_name = req.stage or "No Stage"
                    grouped_requests.setdefault(stage_name, []).append(req)

            elif groupby == 'assignee':
                for req in parts_requests:
                    if req.task_id and req.task_id.user_ids:
                        engineer_names = ', '.join(user.name for user in req.task_id.user_ids)
                        grouped_requests.setdefault(engineer_names, []).append(req)
                    else:
                        grouped_requests.setdefault("Unassigned", []).append(req)

            elif groupby == 'product':
                for req in parts_requests:
                    product_name = req.product_id.name if req.product_id else "No Product"
                    grouped_requests.setdefault(product_name, []).append(req)

            elif groupby == 'part':
                for req in parts_requests:
                    part_name = req.part_name or "No Part Name"
                    grouped_requests.setdefault(part_name, []).append(req)

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
            'product': {'label': 'Product Name'},
            'part': {'label': 'Part Name'},
        }.items():
            combined_options[f'g_{key}'] = {
                'label': f"{val['label']}",
                'groupby': key,
                'filterby': filterby,
            }
        values = {
            'parts_requests': parts_requests,
            'page_name': 'parts_request',
            'sortby': sortby,
            'filterby': filterby,
            'groupby': groupby,
            'search': search,
            'search_in': 'name',
            'sortings': sortings,
            'filters': filters,
            'grouped_requests': grouped_requests,
            'searchbar_inputs': [{'input': 'name', 'label': 'Search'}],
            'searchbar_filters': filters,
            'searchbar_groupby': {
                'none': {'input': 'none', 'label': 'None'},
                'stage': {'input': 'stage', 'label': 'Stage'},
                'assignee': {'input': 'assignee', 'label': 'Assignee'},
                'task': {'input': 'task', 'label': 'Task Name'},
                'product': {'input': 'product', 'label': 'Product Name'},
                'part': {'input': 'part', 'label': 'Part Name'},
            },
            'searchbar_combined': combined_options,
            'default_url': '/my/parts/request',
            'format_date': lambda date: format_date(request.env, date, date_format='dd/MM/yyyy') if date else 'N/A',
        }
        return request.render("parts_request.parts_request_list_view", values)


    @http.route('/my/parts/request/<int:request_id>/approve', type='http', auth="user", website=True, methods=['POST'],
                csrf=True)
    def parts_request_approve(self, request_id, **kwargs):
        """Approve a parts request"""
        partner = request.env.user.partner_id
        part_request = request.env['part.customer.approval.notification'].sudo().browse(request_id)
        if not part_request.exists():
            return request.redirect('/my/parts/request')
        if part_request.task_id.partner_id != partner:
            return request.redirect('/my/parts/request')
        part_request.action_approve()
        part_name = part_request.part_name
        if part_name:
            product_template = request.env['product.template'].sudo().search([
                ('name', '=', part_name),
                ('is_part', '=', True)
            ], limit=1)
            if product_template:
                if product_template.is_part and not product_template.payment_required_first:
                    task = part_request.task_id
                    if task.user_ids:
                        message = _(
                            "Customer %s has approved a parts request for part '%s'."
                        ) % (partner.name, part_name)
                        task.message_post(
                            body=message,
                            partner_ids=task.user_ids.mapped('partner_id').ids,
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment',
                        )
        return request.redirect('/my/parts/request')

    @http.route('/my/parts/request/<int:request_id>/reject', type='http', auth="user", website=True, methods=['POST'],
                csrf=True)
    def parts_request_reject(self, request_id, **kwargs):
        """Reject a parts request"""
        partner = request.env.user.partner_id
        part_request = request.env['part.customer.approval.notification'].sudo().browse(request_id)
        if not part_request.exists():
            return request.redirect('/my/parts/request')
        if part_request.task_id.partner_id != partner:
            return request.redirect('/my/parts/request')
        part_request.action_reject()
        return request.redirect('/my/parts/request')

    @http.route(['/my/view'], type='http', auth='user', website=True)
    def my_tickets(self, sortby='name', filterby='all', groupby='', search='', **kwargs):

        # Get the original render result
        response = PortalHomePage().my_tickets(sortby, filterby, groupby, search, **kwargs)

        # We can access the rendering context via qcontext if it's a TemplateResponse
        if hasattr(response, 'qcontext'):
            qcontext = response.qcontext

            calls = qcontext.get('calls')
            if calls:
                notification_model = request.env['part.approval.notification'].sudo()
                notifications = notification_model.search([('task_id', 'in', calls.ids)])

                print("\n========== DEBUG: NOTIFICATION FETCH (INHERITED) ==========")
                print("Total Tasks:", len(calls))
                print("Task IDs:", calls.ids)
                print("Fetched Notifications:", notifications.ids)

                for n in notifications:
                    part_display = 'N/A'
                    if hasattr(n, 'part_id') and n.part_id:
                        part_display = getattr(n.part_id, 'part_name', False) or \
                                       (getattr(n.part_id, 'product_id', False)
                                        and n.part_id.product_id.display_name) or \
                                       'Unknown Part'
                    print(
                        f"Notification ID={n.id}, Task={n.task_id.id if n.task_id else 'No Task'}, "
                        f"Status={n.status}, Part={part_display}, "
                        f"User={n.create_uid.name if n.create_uid else 'No User'}"
                    )
                print("=================================================\n")

                # ✅ Create task-notification mapping
                notifications_by_task = {n.task_id.id: n for n in notifications}
                qcontext['notifications_by_task'] = notifications_by_task

            # ✅ Finally, return updated response
            return response

        return response

    @http.route('/part/receive/<int:notification_id>', type='http', auth='user', website=True)
    def receive_part(self, notification_id, **kw):
        """Handle the Receive button logic"""
        print("\n========== RECEIVE PART CALLED ==========")
        print("Notification ID:", notification_id)

        notification = request.env['part.approval.notification'].sudo().browse(notification_id)
        if not notification.exists():
            print("Notification not found!")
            return request.not_found()

        # Update statuses
        notification.status = 'received'
        if notification.part_id:
            notification.part_id.status = 'received'

        task = notification.task_id
        print("Related Task:", task.name if task else "No Task")

        # Post message in task chatter
        if task:
            part_name = (
                notification.part_id.product_id.display_name
                or notification.part_id.display_name
                or getattr(notification.part_id, 'part_name', False)
                or _("Unnamed Part")
            )
            task.message_post(
                body=f"Customer received part: <b>{part_name}</b>"
            )
            print("Posted message to task:", task.name)
            print("Part name:", part_name)

        supervisor_user = None
        department_name = None
        if task:
            if task.department_id:
                department_name = task.department_id.name
                supervisor_user = task.department_id.manager_id.user_id
                print("Department found:", department_name)
                print("Supervisor (Manager):", supervisor_user.name if supervisor_user else "No Supervisor found")
            else:
                print("No department linked to task!")


        if supervisor_user:
            print("Creating supervisor notification...")

            message_body = _(
                "Part %s for ticket %s has been marked as Received by the customer %s."
            ) % (part_name, task.name,task.partner_id.name)

            # Post notification as internal message
            task.message_notify(
                body=message_body,
                partner_ids=[supervisor_user.partner_id.id],
                subtype_xmlid='mail.mt_comment',
            )

            print("Notification sent to Supervisor:", supervisor_user.name)
        else:
            print("No Supervisor notification sent (Supervisor not found)")

        print("==========================================\n")
        return request.redirect('/my/view')
