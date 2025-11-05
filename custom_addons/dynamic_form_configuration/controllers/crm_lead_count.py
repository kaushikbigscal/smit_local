# from odoo import http
# from odoo.http import request
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class LeadAPIController(http.Controller):
#
#     @http.route('/web/leads_counts', type='json', auth='user')
#     def get_leads_stats(self, domain=None):
#         try:
#             Lead = request.env['crm.lead'].sudo()
#             current_user = request.env.user
#
#             # Default domain to show only leads (not opportunities)
#             base_domain = ['|', ('type', '=', 'lead'), ('type', '=', False)]
#
#             # Apply incoming domain (e.g., for activity filters)
#             if domain:
#                 if not isinstance(domain, list):
#                     raise ValueError("Domain must be a list.")
#                 base_domain += domain
#
#             # Check user groups
#             is_user_all_docs = current_user.has_group('sales_team.group_sale_salesman_all_leads')
#             is_admin = current_user.has_group('sales_team.group_sale_manager')
#             is_user = current_user.has_group('sales_team.group_sale_salesman')
#
#             # Apply user-based filtering
#             if is_user and not is_user_all_docs and not is_admin:
#                 base_domain += [('user_id', '=', current_user.id)]
#
#             _logger.debug("Final computed domain for lead stats: %s", base_domain)
#
#             # Perform counts
#             active_count = Lead.search_count(base_domain + [('active', '=', True)])
#             archived_count = Lead.search_count(base_domain + [('active', '=', False)])
#             lost_count = Lead.search_count(base_domain + [('active', '=', False), ('probability', '=', 0)])
#             unassigned_count = Lead.search_count(base_domain + [('user_id', '=', False), ('active', '=', True)])
#
#             return {
#                 'success': True,
#                 'data': {
#                     'active': active_count,
#                     'archived': archived_count,
#                     'lost': lost_count,
#                     'unassigned': unassigned_count,
#                 }
#             }
#
#         except Exception as e:
#             _logger.exception("Error while fetching lead counts")
#             return {
#                 'success': False,
#                 'error': str(e)
#             }


from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class LeadAPIController(http.Controller):

    @http.route('/web/leads_counts', type='json', auth='user')
    def get_leads_stats(self, domain=None):
        try:
            Lead = request.env['crm.lead'].sudo()
            current_user = request.env.user
            today = fields.Date.today()

            # Default domain: include leads only (not opportunities)
            base_domain = ['|', ('type', '=', 'lead'), ('type', '=', False)]

            # Add frontend filters if provided
            if domain:
                if not isinstance(domain, list):
                    raise ValueError("Domain must be a list.")
                base_domain += domain

            # User role restrictions
            is_user_all_docs = current_user.has_group('sales_team.group_sale_salesman_all_leads')
            is_admin = current_user.has_group('sales_team.group_sale_manager')
            is_user = current_user.has_group('sales_team.group_sale_salesman')

            if is_user and not is_user_all_docs and not is_admin:
                base_domain += [('user_id', '=', current_user.id)]

            _logger.debug("Final domain for lead stats: %s", base_domain)

            # Regular counts
            active_count = Lead.search_count(base_domain + [('active', '=', True), ('user_id', '!=', False)])
            archived_count = Lead.search_count(base_domain + [('active', '=', False)])
            lost_count = Lead.search_count(base_domain + [('active', '=', False), ('probability', '=', 0)])
            unassigned_count = Lead.search_count(base_domain + [('user_id', '=', False), ('active', '=', True)])

            leads = Lead.search(base_domain)
            my_activity_leads = set(
                lead.id
                for lead in leads
                if any(activity.user_id.id == current_user.id for activity in lead.activity_ids)
            )
            my_activity_count = len(my_activity_leads)
            # Other Activity Counts (using my_activity_date_deadline)
            late_activity_count = Lead.search_count(base_domain + [('my_activity_date_deadline', '<', today)])
            today_activity_count = Lead.search_count(base_domain + [('my_activity_date_deadline', '=', today)])
            future_activity_count = Lead.search_count(base_domain + [('my_activity_date_deadline', '>', today)])

            return {
                'success': True,
                'data': {
                    'active': active_count,
                    'archived': archived_count,
                    'lost': lost_count,
                    'unassigned': unassigned_count,
                    'my_activity': my_activity_count,
                    'late_activity': late_activity_count,
                    'today_activity': today_activity_count,
                    'future_activity': future_activity_count,
                }
            }

        except Exception as e:
            _logger.exception("Error while fetching lead counts")
            return {
                'success': False,
                'error': str(e)
            }
