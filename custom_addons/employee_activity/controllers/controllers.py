import logging

from odoo import http
from odoo.http import request


class EmployeeActivityController(http.Controller):

    @http.route('/api/employee/activities', type='json', auth='user')
    def get_employee_activities(self, parent_employee_id):
        """
        Fetch all activities related to the parent employee and their assigned employees.
        Activities can be from any model (CRM, Sale, Project, etc.).
        """
        try:
            # Find the parent employee
            parent_employee = request.env['hr.employee'].browse(parent_employee_id)
            if not parent_employee.exists():
                return {'error': f"Parent Employee with ID {parent_employee_id} not found."}

            # Get all employees under the parent employee (using parent_id)
            assigned_employees = request.env['hr.employee'].search([('parent_id', '=', parent_employee.id)])

            all_employee_ids = assigned_employees.ids + [parent_employee.id]  # Include parent employee

            # Fetch all activities related to these employees
            activities = request.env['mail.activity'].search([
                ('user_id.employee_id', 'in', all_employee_ids)
            ])

            # Extract relevant data
            activities_data = activities.read(
                ['summary', 'activity_type_id', 'res_model', 'res_id', 'date_deadline', 'user_id'])
            activities_result = []

            for activity in activities_data:
                # For each activity, retrieve model details (CRM, Sale, Project, etc.)
                activity_details = {
                    'summary': activity['summary'],
                    'activity_type': activity['activity_type_id'][1] if activity['activity_type_id'] else None,
                    'model': activity['res_model'],
                    'res_id': activity['res_id'],
                    'date_deadline': activity['date_deadline'],
                    'assigned_user': activity['user_id']
                }
                activities_result.append(activity_details)

            result = {
                'parent_employee': parent_employee.name,
                'assigned_employees': assigned_employees.mapped('name'),
                'activities': activities_result,
            }
            return {
                'status': 'success',
                'result': result
            }

        except Exception as e:
            message = {str(e)}
            return {
                'status': 'false',
                'error': message
            }


# {
#     "jsonrpc": "2.0",
#     "method": "call",
#     "params": {
#         "parent_employee_id": 1  // Replace with the parent employee's ID
#     },
#     "id": 1
# }


_logger = logging.getLogger(__name__)


# class MenuController(http.Controller):
#
#     @http.route('/api/user_menus', type='json', auth='user', csrf=False)
#     def get_user_menus(self):
#         _logger.info("get_user_menus called")  # Log when the method is called
#
#         # Fetch the current user
#         user = request.env.user
#
#         # Log the user ID and type for debugging
#         _logger.info("Current user ID: %s, Type: %s", user.id, type(user))
#
#         # Check if user is a record and has groups_id
#         if not user or not hasattr(user, 'groups_id'):
#             return {'error': 'User not found or does not have groups_id attribute.'}
#
#         # Get all parent menu items
#         all_parent_menus = request.env['ir.ui.menu'].search([
#             ('active', '=', True),
#             ('parent_id', '=', False)  # Only fetch parent menus
#         ])
#
#         # Filter menus based on user access rights
#         accessible_menus = []
#         for menu in all_parent_menus:
#             if menu.groups_id and any(group in user.groups_id.ids for group in menu.groups_id.ids):
#                 accessible_menus.append({
#                     'id': menu.id,
#                     'name': menu.name,
#                     'sequence': menu.sequence,
#                 })
#
#         return {'menus': accessible_menus}

class MenuAPI(http.Controller):

    @http.route('/api/user/menus', type='json', auth='user', csrf=False)
    def get_user_menus(self, user_id):
        """
        Fetch menus based on user's group permissions.
        First gets user groups, then fetches accessible menus.
        """
        try:
            # user_id = kwargs.get('user_id')
            if not user_id:
                return {'status': 'error', 'message': 'User ID is required'}

            user = request.env['res.users'].sudo().browse(int(user_id))
            if not user.exists():
                return {'status': 'error', 'message': 'User not found'}

            # First get user's groups
            user_groups = self._get_user_groups(user)
            if not user_groups:
                return {'status': 'error', 'message': 'No groups found for user'}

            # Then get menus based on groups
            menu_data = self._get_group_based_menus(user_groups)

            return {
                'status': 'success',
                'data': {
                    'user': {
                        'id': user.id,
                        'name': user.name,
                        'login': user.login,
                    },
                    'menus': menu_data
                }
            }

        except Exception as e:
            _logger.error(f"Error fetching menus: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _get_user_groups(self, user):
        """Fetch all groups associated with the user."""
        return user.groups_id

    def _get_group_based_menus(self, user_groups):
        """Fetch menus based on user groups."""
        Menu = request.env['ir.ui.menu'].sudo()
        group_ids = user_groups.ids

        # Build domain for menus accessible by user groups
        domain = ['|', ('groups_id', '=', False), ('groups_id', 'in', group_ids)]

        # Get all accessible menus
        all_menus = Menu.search(domain)

        # First, get all accessible menu IDs
        accessible_menu_ids = set()
        for menu in all_menus:
            # Add the menu and all its parents to make sure we have complete paths
            current = menu
            while current:
                accessible_menu_ids.add(current.id)
                current = current.parent_id

        # Now build the tree structure starting with root menus
        root_menus = Menu.search([
            ('id', 'in', list(accessible_menu_ids)),
            ('parent_id', '=', False)
        ], order='sequence')

        return [self._format_menu_tree(menu, accessible_menu_ids) for menu in root_menus]

    def _format_menu_tree(self, menu, accessible_menu_ids):
        """Format menu tree with only accessible menus."""
        menu_data = {
            'id': menu.id,
            'name': menu.name,
            'sequence': menu.sequence,
            'web_icon': menu.web_icon or None,
            'children': []
        }

        # Add action information if exists
        if menu.action:
            menu_data['action'] = {
                'id': menu.action.id,
                'name': menu.action.name,
                'type': menu.action.type,
            }

        # Add children recursively if they're in accessible_menu_ids
        for child in menu.child_id:
            if child.id in accessible_menu_ids:
                child_menu = self._format_menu_tree(child, accessible_menu_ids)
                menu_data['children'].append(child_menu)

        # Sort children by sequence
        menu_data['children'].sort(key=lambda x: x.get('sequence', 100))

        return menu_data


# class MenuAPI(http.Controller):
#
#     @http.route('/api/menus', type='json', auth='user', csrf=False)
#     def get_menus(self, user_id):
#         """
#         Fetch menus and submenus for a specific user.
#         The user ID must be provided in the request body as 'user_id'.
#         """
#
#         if not user_id:
#             return {'status': 'error', 'message': 'User ID is required.'}
#
#             # Get the user record
#         user = request.env['res.users'].browse(user_id)
#
#         if not user.exists():
#             return {'status': 'error', 'message': 'Invalid user ID.'}
#
#         # Fetch menus for the user
#         menu_data = self._fetch_menus(user)
#         return {'status': 'success', 'data': menu_data}
#
#     def _fetch_menus(self, user):
#         """Fetch menus and submenus based on user access."""
#         menus = request.env['ir.ui.menu'].search([('parent_id', '=', False)], order="sequence")
#
#         # Filter menus based on user groups
#         accessible_menus = []
#         for menu in menus:
#             # Check if the user can access this menu (based on groups)
#             if self._user_can_access_menu(user, menu):
#                 accessible_menus.append(self._format_menu(menu, user))
#         return accessible_menus
#
#     def _user_can_access_menu(self, user, menu):
#         """Check if the user can access a menu based on their groups."""
#         # Check if the user is a member of any group that has access to this menu
#         if user.has_group('base.group_user'):
#             return True  # Simplified, you can add specific checks for group access here
#         return False  # Adjust this logic as needed
#
#     def _format_menu(self, menu, user):
#         """Format a menu and its submenus recursively."""
#         return {
#             'id': menu.id,
#             'name': menu.name,
#             'parent_id': menu.parent_id.id if menu.parent_id else None,
#             'action': menu.action.id if menu.action else None,
#             'children': [
#                 self._format_menu(child, user) for child in menu.child_id if self._user_can_access_menu(user, child)
#             ]
#         }
