from odoo import http, fields
from odoo.http import request
from odoo.service import security
import werkzeug.wrappers
from datetime import datetime, time
from pytz import timezone
import logging

_logger = logging.getLogger(__name__)


class GetSessionController(http.Controller):

    @http.route('/web/get_session_id', type='json', auth='user')
    def get_session_id(self):
        session_id = request.httprequest.cookies.get('session_id')
        csrf_token = request.csrf_token()
        return {'session_id': session_id,
                'csrf_token': csrf_token}


class AllAccessRightsController(http.Controller):
    @http.route('/web/check_all_access_rights', type='json', auth='user')
    def check_all_access_rights(self, model_name):
        """
        API to check a user's access rights on a given model.

        :param model_name: Odoo model name (e.g., 'res.partner')
        :return: Dictionary containing access rights for CRUD operations
        """
        if not model_name:
            return {"status": False, "error": "Model name is required"}

        # Validate if the model exists
        if model_name not in request.env:
            return {"status": False, "error": f"Invalid model name: {model_name}"}

        result = {}
        operations = ["create", "read", "write", "unlink"]

        for operation in operations:
            try:
                result[operation] = request.env[model_name].check_access_rights(operation, raise_exception=False)
            except Exception as e:
                result[operation] = False  # Instead of exposing raw errors, return False

        return {"status": True, "access_rights": result}

    # def get_access_rights(self):
    #     models = ['crm.lead', 'project.task', 'hr.leave']
    #     perms = ['read', 'write', 'create', 'unlink']
    #     result = {}
    #     for model in models:
    #         result[model] = {}
    #         for perm in perms:
    #             result[model][perm] = request.env[model].check_access_rights(perm, raise_exception=False)
    #     return result


# class UserGroupController(http.Controller):
#     @http.route('/web/get_user_groups', type='json', auth='user')
#     def get_user_groups(self):
#         """
#         API to retrieve user groups organized by module.
#
#         :return: Dictionary with module names as keys and user group names as values
#         """
#         try:
#             user = request.env.user
#             groups = user.groups_id  # Get all groups assigned to the user
#
#             module_wise_groups = {}
#
#             for group in groups:
#                 module_name = group.category_id.name if group.category_id else "Other"
#                 if module_name not in module_wise_groups:
#                     module_wise_groups[module_name] = []
#                 module_wise_groups[module_name].append(group.name)
#
#             return {"success": True, "user_groups": module_wise_groups}
#
#         except Exception as e:
#             return {"success": False, "error": str(e)}

class UserModuleGroups(http.Controller):
    @http.route('/web/get_user_groups', type='json', auth='user')
    def get_user_module_groups(self):
        """
        API to fetch all user groups organized by the modules they belong to,
        including their inherited (implied) groups.
        """
        try:
            env = request.env
            user = env.user

            # Step 1: Get all groups the user belongs to
            user_group_ids = user.groups_id.ids  # List of user's group IDs

            if not user_group_ids:
                return {"success": True, "modules": {}}

            # Step 2: Fetch module names and group records from ir.model.data
            group_data = env['ir.model.data'].sudo().search_read(
                [('model', '=', 'res.groups'), ('res_id', 'in', user_group_ids)],
                ['res_id', 'name', 'module']
            )

            # Step 3: Organize groups by module and include implied groups
            module_groups = {}
            for record in group_data:
                module_name = record['module'] or "Other"
                if module_name not in module_groups:
                    module_groups[module_name] = []

                # Fetch actual group details
                group = env['res.groups'].sudo().browse(record['res_id'])
                if group.exists():
                    module_groups[module_name].append({
                        "name": group.name,
                        "implied_ids": group.implied_ids.mapped('name')  # List of inherited group names
                    })

            return {"success": True, "modules": module_groups}

        except Exception as e:
            return {"success": False, "error": str(e)}


class CustomAuthController(http.Controller):

    @http.route('/web/session/authenticate', type='json', auth="none", csrf=False)
    def authenticate(self, db, login, password):
        try:
            # Call the original authentication method
            uid = request.session.authenticate(db, login, password)
            if uid:

                # Get the default response
                default_response = request.env['ir.http'].session_info()

                # Add attendance records if the user is an employee
                user = request.env['res.users'].sudo().browse(uid)
                image_data = user.image_1920
                if image_data:
                    default_response['profile_image'] = image_data
                # -------------------------------------------------------------------------------------
                company_id = user.company_id.id if user.company_id else False

                # Fetch the company details using the dynamic company ID
                company = request.env['res.company'].sudo().search([('id', '=', company_id)],
                                                                   limit=1) if company_id else None

                if company:
                    # Fetch the fields like enable_geofence, latitude, longitude, allowed_distance, etc.
                    default_response['company_geofence_info'] = {
                        'enable_geofence': company.enable_geofence,
                        'enable_geofence_day_out': company.enable_geofence_day_out,
                        'company_latitude': company.company_latitude,
                        'company_longitude': company.company_longitude,
                        'allowed_distance': company.allowed_distance,
                        'display_name': company.display_name
                    }
                # Fetch user-specific geofencing settings
                if user:
                    default_response['user_geofence_info'] = {
                        'enable_geofence': user.enable_geofence,
                        'enable_geofence_day_out': user.enable_geofence_day_out,
                        # 'enable_gps_tracking': user.enable_gps_tracking,
                    }

                # -------------------------------------------------------------------------------------

                employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

                if employee:
                    # Get the user's timezone
                    user_tz = timezone(user.tz or 'UTC')

                    # Get the current date in the user's timezone
                    current_date = datetime.now(user_tz).date()

                    # Define the start and end of the current day in the user's timezone
                    day_start = user_tz.localize(datetime.combine(current_date, time.min))
                    day_end = user_tz.localize(datetime.combine(current_date, time.max))

                    # Convert to UTC for the database query
                    day_start_utc = day_start.astimezone(timezone('UTC'))
                    day_end_utc = day_end.astimezone(timezone('UTC'))

                    attendance_records = request.env['hr.attendance'].sudo().search_read(
                        [
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', day_start_utc),
                            ('check_in', '<=', day_end_utc)
                        ],
                        ['check_in', 'check_out'],
                        order='check_in desc'
                    )

                    # Convert times back to user's timezone for display
                    for record in attendance_records:
                        if record['check_in']:
                            record['check_in'] = timezone('UTC').localize(record['check_in']).astimezone(
                                user_tz).strftime('%Y-%m-%d %H:%M:%S')
                        if record['check_out']:
                            record['check_out'] = timezone('UTC').localize(record['check_out']).astimezone(
                                user_tz).strftime('%Y-%m-%d %H:%M:%S')

                    default_response['attendance_records'] = attendance_records

                    # -------------------for department name and id -------------------

                    user = request.env['res.users'].sudo().browse(uid)
                    employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                    if not employee:
                        return None

                    employee_info = {
                        'department_id': employee.department_id.id if employee.department_id else False,
                        'department_name': employee.department_id.name if employee.department_id else False
                    }
                    default_response['department_info'] = employee_info
                # ---------------------------------------------------------------------------

                try:
                    # Safe read of system parameter
                    time_interval = int(
                        request.env["ir.config_parameter"].sudo().get_param(
                            "field_service_tracking.time_interval", default=5000
                        )
                    )
                    _logger.info("[AUTH] Time interval fetched successfully: %s", time_interval)
                except Exception as e:
                    time_interval = 5000  # fallback
                    _logger.warning("[AUTH] Failed to fetch time interval parameter, using default 5000. Error: %s", e)

                # --------------------------------------------------------------------
                # Check if the field_service_tracking module is installed before using its fields
                try:
                    module_installed = request.env["ir.module.module"].sudo().search_count([
                        ("name", "=", "field_service_tracking"),
                        ("state", "=", "installed")
                    ]) > 0
                    _logger.info("[AUTH] field_service_tracking module installed: %s", module_installed)
                except Exception as e:
                    module_installed = False
                    _logger.error("[AUTH] Error checking module installation: %s", e)

                # --------------------------------------------------------------------
                try:
                    if module_installed:
                        if "enable_gps_tracking" in request.env["res.users"]._fields:
                            enable_gps_tracking = bool(user.sudo().enable_gps_tracking)
                            _logger.info("[AUTH] enable_gps_tracking field found, value: %s", enable_gps_tracking)
                    else:
                        enable_gps_tracking = False
                        if not module_installed:
                            _logger.info(
                                "[AUTH] field_service_tracking module not installed, skipping GPS tracking flag.")
                        else:
                            _logger.info("[AUTH] enable_gps_tracking field not found in res.users model.")
                except Exception as e:
                    enable_gps_tracking = False
                    _logger.error("[AUTH] Error reading enable_gps_tracking field: %s", e)

                # try:
                #     # Safe read of system parameter
                #     time_interval = int(
                #         request.env["ir.config_parameter"].sudo().get_param(
                #             "field_service_tracking.time_interval", default=5000
                #         )
                #     )
                #     logger.info("1", time_interval)
                # except Exception:
                #     time_interval = 5000  # fallback
                #
                # # Check if the field_service_tracking module is installed before using its fields
                # module_installed = request.env["ir.module.module"].sudo().search_count([
                #     ("name", "=", "field_service_tracking"),
                #     ("state", "=", "installed")
                # ]) > 0
                # logger.info('module_installed', module_installed.value())
                #
                # if module_installed and "enable_gps_tracking" in request.env["res.users"]._fields:
                #     enable_gps_tracking = bool(user.sudo().enable_gps_tracking)
                # else:
                #     logger.info("else case")
                #     enable_gps_tracking = False

                default_response["time_interval"] = time_interval
                default_response["enable_gps_tracking"] = enable_gps_tracking

                # ---------------------------------------------------------------------------

                return default_response
            else:
                return werkzeug.wrappers.Response(status=401, content_type='application/json')
        except Exception as e:
            return werkzeug.wrappers.Response(status=500, content_type='application/json')


import pytz
import json
from lxml import etree


class CustomAPIController(http.Controller):
    # original
    @http.route('/web/user_dashboard_counts', type='json', auth='user')
    def get_user_dashboard_counts(self):
        try:
            try:
                request_data = json.loads(request.httprequest.data.decode('utf-8'))
                params = request_data.get('params', {})
                args = params.get('args', [])
                user_data = args[0] if args else {}
                user_id = user_data.get('user_id')

                # Validate user_id
                if not user_id:
                    raise ValueError("Missing 'user_id' in the request parameters.")
            except Exception as parse_error:
                return parse_error

            # Fetch counts with error handling
            try:
                lead_count = request.env['crm.lead'].sudo().search_count([
                    ('user_id', '=', user_id),
                    ('type', '=', 'lead'),
                    ("active", "=", True),
                ])

                task_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ("display_in_project", "=", True),
                    ("is_fsm", "=", False),
                    ("active", "=", True),
                    ("state", "in", ["01_in_progress", "02_changes_requested", "03_approved", "05_not_started"]),
                ])

                opportunity_count = request.env['crm.lead'].sudo().search_count([
                    ('type', '=', 'opportunity'),
                    ('user_id', '=', user_id),
                    ("active", "=", True),
                ])

                project_count = request.env['project.project'].sudo().search_count([
                    ('user_id', '=', user_id),
                    ("is_fsm", "=", False),
                    ("active", "=", True),
                    ('is_internal_project', '=', False),
                    ("is_project_template", "=", False)
                ])

                todo_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ('project_id', '=', False),
                    ("parent_id", "=", False),
                    ("active", "=", True),
                    ("state", "not in", ['1_done', '1_canceled']),
                ])

                call_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ("project_id", "!=", False),
                    ('display_in_project', '=', True),
                    ("is_fsm", "=", True),
                    ("active", "=", True),
                    ("stage_id", "not in", ['Done', 'Canceled']),

                ])
            except Exception as query_error:
                message = {str(query_error)}
                return {
                    'status': 'false',
                    'error': message
                }

            result = {
                'lead_count': lead_count,
                'opportunity_count': opportunity_count,
                'project_count': project_count,
                'task_count': task_count,
                'todo_count': todo_count,
                'call_count': call_count
            }

            return {
                'status': 'success',
                'result': result

            }

        except Exception as e:
            # Catch any unexpected errors
            message = {str(e)}
            return {
                'status': 'false',
                'error': message
            }


# from odoo import http
# from odoo.http import request
# import json
#
#
# class CustomControllerApi(http.Controller):
#
#     @http.route('/web/user_dashboard_counts', type='json', auth='user', csrf=False)
#     def get_user_dashboard_counts(self):
#         try:
#             request_data = json.loads(request.httprequest.data.decode('utf-8'))
#             params = request_data.get('params', {})
#             args = params.get('args', [])
#             user_data = args[0] if args else {}
#             user_id = user_data.get('user_id')
#
#             if not user_id:
#                 raise ValueError("Missing 'user_id' in the request parameters.")
#
#             result = {}
#
#             count_config = {
#                 'lead_count': {
#                     'model': 'crm.lead',
#                     'domain': [('user_id', '=', user_id), ('type', '=', 'lead')],
#                 },
#                 'opportunity_count': {
#                     'model': 'crm.lead',
#                     'domain': [('user_id', '=', user_id), ('type', '=', 'opportunity')],
#                 },
#                 'project_count': {
#                     'model': 'project.project',
#                     'domain': [('user_id', '=', user_id), ('is_fsm', '=', False)],
#                 },
#                 'task_count': {
#                     'model': 'project.task',
#                     'domain': [
#                         ('user_ids', 'in', [user_id]),
#                         ('display_in_project', '=', True),
#                         ('is_fsm', '=', False),
#                         ('state', 'not in', ['1_done', '1_canceled']),
#                     ],
#                 },
#                 'todo_count': {
#                     'model': 'project.task',
#                     'domain': [
#                         ('user_ids', 'in', [user_id]),
#                         ('project_id', '=', False),
#                         ('parent_id', '=', False),
#                         ('state', 'not in', ['1_done', '1_canceled']),
#                     ],
#                 },
#                 'call_count': {
#                     'model': 'project.task',
#                     'domain': [
#                         ('user_ids', 'in', [user_id]),
#                         ('project_id', '!=', False),
#                         ('display_in_project', '=', True),
#                         ('is_fsm', '=', True),
#                         ('stage_id.name', 'not in', ['Done', 'Canceled']),
#                     ],
#                 },
#             }
#
#             for key, cfg in count_config.items():
#                 model_name = cfg['model']
#                 domain = cfg['domain']
#
#                 try:
#                     model = request.env[model_name]
#                     # Explicitly check read access rights
#                     x = model.check_access_rights('read', raise_exception=True)
#                     print(x)
#                     count = model.search_count(domain)
#                     result[key] = count
#                 except Exception:
#                     # No access — set count to 0
#                     result[key] = 0
#
#             return {
#                 'status': 'success',
#                 'result': result
#             }
#
#         except Exception as e:
#             return {
#                 'status': 'false',
#                 'error': str(e)
#             }


# class CustomApiController(http.Controller):
#
#     @http.route('/web/user_data', type='json', auth='user', csrf=False)
#     def handle_combined_api(self, date_start, date_end, user_id):
#         ist_tz = pytz.timezone('Asia/Kolkata')
#
#         # Parse input dates
#         start_date = datetime.strptime(date_start, '%Y-%m-%d')
#         end_date = datetime.strptime(date_end, '%Y-%m-%d')  # Make sure to use date_end here
#
#         # Create naive datetime objects with desired times
#         start_naive = start_date.replace(hour=0, minute=0, second=0)
#         end_naive = end_date.replace(hour=23, minute=59, second=59)  # Use end_date here
#
#         # Properly localize to IST
#         start_date_ist = ist_tz.localize(start_naive)
#         end_date_ist = ist_tz.localize(end_naive)
#
#         # Convert to UTC
#         start_date_utc = start_date_ist.astimezone(pytz.UTC)
#         end_date_utc = end_date_ist.astimezone(pytz.UTC)
#
#         # Format for query
#         start_date_query_utc = start_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#         end_date_query_utc = end_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#
#         def rename_fields(records, field_map):
#             for record in records:
#                 for old_field, new_field in field_map.items():
#                     if old_field in record:
#                         record[new_field] = record.pop(old_field)
#             return records
#
#         response = {}
#
#         def fetch_model_data(model, domain, fields, field_map, category_name):
#             try:
#                 records = request.env[model].search_read(domain, fields)
#                 response[category_name] = rename_fields(records, field_map)
#             except Exception as e:
#                 response[category_name] = []  # Return empty if no access
#
#         # Fetch each module separately
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["is_fsm", "=", False]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'tasks'
#         )
#
#         fetch_model_data(
#             'crm.lead',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["type", "=", "lead"]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'leads'
#         )
#
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["is_fsm", "=", True]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'service_calls'
#         )
#
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["project_id", "=", False], ["parent_id", "=", False]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'todo_tasks'
#         )
#
#         fetch_model_data(
#             'crm.lead',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["type", "=", "opportunity"], ["active", "=", True]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'opportunities'
#         )
#
#         fetch_model_data(
#             'project.project',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ['is_internal_project', '=', False]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'projects'
#         )
#
#         # Process user_ids and tag_ids for records
#         for category in ['tasks', 'leads', 'service_calls', 'todo_tasks', 'opportunities', 'projects']:
#             for record in response.get(category, []):
#                 if 'user_ids' in record and isinstance(record['user_ids'], list):
#                     users = request.env['res.users'].browse(record['user_ids'])
#                     record['user_ids'] = [{'id': user.id, 'name': user.name} for user in users]
#
#                 if category in ['tasks', 'todo_tasks', 'projects', 'service_calls']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['project.tags'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
#
#                 elif category in ['leads', 'opportunities']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['crm.tag'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
#
#         return {
#             'status': 'success',
#             'result': response,
#         }

# ========== this is work until assigned by me ==================
# class CustomApiController(http.Controller):
#
#     @http.route('/web/user_data', type='json', auth='user', csrf=False)
#     def handle_combined_api(self, date_start=None, date_end=None, user_id=None, assigned_by_me=False):
#         ist_tz = pytz.timezone('Asia/Kolkata')
#         current_user_id = request.env.uid
#
#         # Initialize date domain
#         date_domain = []
#
#         # Add date filters if provided
#         if date_start and date_end:
#             # Parse input dates
#             start_date = datetime.strptime(date_start, '%Y-%m-%d')
#             end_date = datetime.strptime(date_end, '%Y-%m-%d')
#
#             # Create naive datetime objects with desired times
#             start_naive = start_date.replace(hour=0, minute=0, second=0)
#             end_naive = end_date.replace(hour=23, minute=59, second=59)
#
#             # Properly localize to IST
#             start_date_ist = ist_tz.localize(start_naive)
#             end_date_ist = ist_tz.localize(end_naive)
#
#             # Convert to UTC
#             start_date_utc = start_date_ist.astimezone(pytz.UTC)
#             end_date_utc = end_date_ist.astimezone(pytz.UTC)
#
#             # Format for query
#             start_date_query_utc = start_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#             end_date_query_utc = end_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#
#             date_domain = [
#                 ["create_date", ">=", start_date_query_utc],
#                 ["create_date", "<=", end_date_query_utc]
#             ]
#
#         def rename_fields(records, field_map):
#             for record in records:
#                 for old_field, new_field in field_map.items():
#                     if old_field in record:
#                         record[new_field] = record.pop(old_field)
#             return records
#
#         response = {}
#
#         def fetch_model_data(model, base_domain, fields, field_map, category_name):
#             try:
#                 # Starting with base domain and date domain
#                 domain = base_domain + date_domain
#                 records = request.env[model].search_read(domain, fields)
#                 response[category_name] = rename_fields(records, field_map)
#             except Exception as e:
#                 response[category_name] = []  # Return empty if no access
#
#         # Get excluded user IDs (all users except current user)
#         excluded_user_ids = request.env['res.users'].search([('id', '!=', current_user_id)]).ids
#
#         # Fetch tasks
#         if assigned_by_me:
#             # Tasks assigned by me to others
#             task_assigned_by_me_domain = [
#                 ("is_fsm", "=", False),
#                 ('create_uid', '=', current_user_id),
#                 ('user_ids', '!=', False),
#                 ('user_ids', 'in', excluded_user_ids)
#             ]
#             fetch_model_data(
#                 'project.task',
#                 task_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#                 {'state': 'status'},
#                 'tasks'
#             )
#         else:
#             # Normal task filtering
#             user_domain = [["user_ids", "in", [user_id]]] if user_id else []
#             fetch_model_data(
#                 'project.task',
#                 [["is_fsm", "=", False]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#                 {'state': 'status'},
#                 'tasks'
#             )
#
#         # Fetch leads
#         if assigned_by_me:
#             # Leads assigned by me to others
#             lead_assigned_by_me_domain = [
#                 ("type", "=", "lead"),
#                 ('create_uid', '=', current_user_id),
#                 ('user_id', '!=', current_user_id),
#                 ('user_id', '!=', False)
#             ]
#             fetch_model_data(
#                 'crm.lead',
#                 lead_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'leads'
#             )
#         else:
#             # Normal lead filtering
#             user_domain = [["user_id", "=", user_id]] if user_id else []
#             fetch_model_data(
#                 'crm.lead',
#                 [["type", "=", "lead"]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'leads'
#             )
#
#         # Fetch service calls
#         if assigned_by_me:
#             # Service calls assigned by me to others
#             service_call_assigned_by_me_domain = [
#                 ["is_fsm", "=", True],
#                 ('create_uid', '=', current_user_id),
#                 ('user_ids', '!=', False),
#                 ('user_ids', 'in', excluded_user_ids)
#             ]
#             fetch_model_data(
#                 'project.task',
#                 service_call_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'service_calls'
#             )
#         else:
#             # Normal service call filtering
#             user_domain = [["user_ids", "in", [user_id]]] if user_id else []
#             fetch_model_data(
#                 'project.task',
#                 [["is_fsm", "=", True]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'service_calls'
#             )
#
#         # Fetch todo tasks
#         if assigned_by_me:
#             # Todo tasks assigned by me to others
#             todo_task_assigned_by_me_domain = [
#                 ["project_id", "=", False],
#                 ["parent_id", "=", False],
#                 ('create_uid', '=', current_user_id),
#                 ('user_ids', '!=', False),
#                 ('user_ids', 'in', excluded_user_ids)
#             ]
#             fetch_model_data(
#                 'project.task',
#                 todo_task_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#                 {'state': 'status'},
#                 'todo_tasks'
#             )
#         else:
#             # Normal todo task filtering
#             user_domain = [["user_ids", "in", [user_id]]] if user_id else []
#             fetch_model_data(
#                 'project.task',
#                 [["project_id", "=", False], ["parent_id", "=", False]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#                 {'state': 'status'},
#                 'todo_tasks'
#             )
#
#         # Fetch opportunities
#         if assigned_by_me:
#             # Opportunities assigned by me to others
#             opportunity_assigned_by_me_domain = [
#                 ["type", "=", "opportunity"],
#                 ["active", "=", True],
#                 ('create_uid', '=', current_user_id),
#                 ('user_id', '!=', current_user_id),
#                 ('user_id', '!=', False)
#             ]
#             fetch_model_data(
#                 'crm.lead',
#                 opportunity_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'opportunities'
#             )
#         else:
#             # Normal opportunity filtering
#             user_domain = [["user_id", "=", user_id]] if user_id else []
#             fetch_model_data(
#                 'crm.lead',
#                 [["type", "=", "opportunity"], ["active", "=", True]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'opportunities'
#             )
#
#         # Fetch projects
#         if assigned_by_me:
#             # Projects assigned by me to others
#             project_assigned_by_me_domain = [
#                 ['is_internal_project', '=', False],
#                 ('create_uid', '=', current_user_id),
#                 ('user_id', '!=', current_user_id),
#                 ('user_id', '!=', False)
#             ]
#             fetch_model_data(
#                 'project.project',
#                 project_assigned_by_me_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'projects'
#             )
#         else:
#             # Normal project filtering
#             user_domain = [["user_id", "=", user_id]] if user_id else []
#             fetch_model_data(
#                 'project.project',
#                 [['is_internal_project', '=', False]] + user_domain,
#                 ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#                 {'stage_id': 'status'},
#                 'projects'
#             )
#
#         # Process user_ids and tag_ids for records
#         for category in ['tasks', 'leads', 'service_calls', 'todo_tasks', 'opportunities', 'projects']:
#             for record in response.get(category, []):
#                 if 'user_ids' in record and isinstance(record['user_ids'], list):
#                     users = request.env['res.users'].browse(record['user_ids'])
#                     record['user_ids'] = [{'id': user.id, 'name': user.name} for user in users]
#
#                 if category in ['tasks', 'todo_tasks', 'projects', 'service_calls']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['project.tags'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
#
#                 elif category in ['leads', 'opportunities']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['crm.tag'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
#
#         return {
#             'status': 'success',
#             'result': response,
#         }


from odoo import http
from odoo.http import request


class FormAPI(http.Controller):

    @http.route('/web/relation_data', type='json', auth='user')
    def get_relation_data(self):
        """
        Fetch data from a related model with optional domain filtering.

        :return: JSON response with related data or error message.
        """

        try:
            # Parse JSON data from the request body
            request_data = request.httprequest.get_json()

            # Extract parameters
            model_name = request_data.get('model_name')
            fields_to_fetch = request_data.get('fields_to_fetch', ['id', 'name', 'display_name'])
            domain = request_data.get('domain', [])  # Expecting a list of tuples

            if not model_name:
                return {'status': 'error', 'message': 'Parameter "model_name" is required.'}

            # Check if the model exists
            if model_name not in request.env:
                return {'status': 'error', 'message': f'Model {model_name} does not exist.'}

            # Fetch records with domain filtering
            records = request.env[model_name].search(domain)
            data = records.read(fields_to_fetch)

            return {'status': 'success', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


# #
# class FormAPI(http.Controller):
#
#     @http.route('/web/form_config', type='json', auth='user')
#     def get_project_form_config(self):
#         try:
#             # Get the request data directly using get_json() method
#             request_data = request.httprequest.get_json()
#
#             # Check if the required parameters are present
#             model = request_data.get('model')
#             view_xml_id = request_data.get('view_xml_id')
#
#             if not model or not view_xml_id:
#                 return {'status': 'error', 'message': 'Model and view_xml_id are required'}
#
#             # Get the view reference dynamically based on the model and view_xml_id
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': 'error', 'message': f'View {view_xml_id} not found'}
#
#             # Get fields info for the model
#             model_obj = request.env[model]
#             fields_data = model_obj.fields_get()
#
#             # Get view architecture with inherited views
#             view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': 'error', 'message': 'View architecture not found'}
#
#             # Parse the XML architecture
#             arch_tree = etree.fromstring(arch)
#
#             # Initialize result fields
#             result_fields = {}
#
#             # Process fields from XML view first to get visibility
#             field_visibility = {}
#             for field in arch_tree.xpath("//field"):
#                 field_name = field.get('name')
#                 if field_name:
#                     field_visibility[field_name] = not field.get('invisible', False)
#
#             # # Combine fields_get data with visibility information
#             # for field_name, field_info in fields_data.items():
#             #     if field_name in field_visibility:
#             #         result_fields[field_name] = {
#             #             'visible': field_visibility[field_name],
#             #             'readonly': field_info.get('readonly', False),
#             #             'required': field_info.get('required', False),
#             #             'string': field_info.get('string', ''),
#             #             'type': field_info.get('type', ''),
#             #             'widget': '',  # Default empty widget as it comes from view
#             #             'domain': field_info.get('domain', []),
#             #             'selection': field_info.get('selection', []),
#             #             'states': field_info.get('states', {})
#             #         }
#             # Fetch 'for_mobile' values dynamically for each field
#             mobile_field_model = request.env['ir.model.fields.mobile']
#
#             # Compare fields and retrieve the 'for_mobile' value
#             for field_name, field_info in fields_data.items():
#                 if field_name in field_visibility:
#                     # Fetch 'for_mobile' value from 'ir.model.fields.mobile'
#                     for_mobile_value = mobile_field_model.get_field_for_mobile(model, field_name)
#                     print(for_mobile_value)
#
#                     result_fields[field_name] = {
#                         'visible': field_visibility[field_name],
#                         'readonly': field_info.get('readonly', False),
#                         'required': field_info.get('required', False),
#                         'string': field_info.get('string', ''),
#                         'type': field_info.get('type', ''),
#                         'widget': '',  # Default empty widget as it comes from view
#                         'domain': field_info.get('domain', []),
#                         'selection': field_info.get('selection', []),
#                         'states': field_info.get('states', {}),
#                         'for_mobile': for_mobile_value  # Use the value from 'for_mobile'
#                     }
#
#             # Remove Chatter fields from the response
#             for chatter_field in ['message_follower_ids', 'message_ids', 'activity_ids']:
#                 if chatter_field in result_fields:
#                     del result_fields[chatter_field]
#
#             return {
#                 'status': 'success',
#                 'fields': result_fields
#             }
#
#         except Exception as e:
#             return {'status': 'error', 'message': str(e)}

# {
#     "jsonrpc": "2.0",
#     "method": "call",
#     "params": {
#         "id_user": 2,
#         "date_start": "2024-07-14"
#     },
#     "id": 1
# }
#
# {
#     "jsonrpc": "2.0",
#     "method": "call",
#     "params": {
#         "args": [
#             {
#                 "user_id": 2
#             }
#         ]
#     },
#     "id": 1
# }

# {
#     "model": "project.task",
#     "view_xml_id": "project_todo.project_task_view_todo_form"
# }


# def process_field(field, field_name):
#     """Process a field and return its domain."""
#     if field is False:
#         return [(field_name, '=', False)]
#     if isinstance(field, list):
#         processed_field = [fid if isinstance(fid, int) else None for fid in field]
#         if None in processed_field:
#             non_null_field = [fid for fid in processed_field if fid is not None]
#             if non_null_field:
#                 return ['|', (field_name, 'in', non_null_field), (field_name, '=', False)]
#             else:
#                 return [(field_name, '=', False)]
#         else:
#             return [(field_name, 'in', processed_field)]
#     else:
#         try:
#             return [(field_name, '=', int(field))]
#         except ValueError:
#             raise ValueError(f"Invalid {field_name} format. Must be an integer or a list of integers/False.")
class ProjectTaskCountAPI(http.Controller):

    @http.route('/web/task/count', type='json', auth='user')
    def task_count(self, user_ids=None, tag_ids=None, company_id=None, milestone_id=None, project_id=None):
        def process_field(field, field_name):
            """Process list fields (user_ids, tag_ids) for domains."""
            if isinstance(field, list):
                non_null_ids = [fid for fid in field if isinstance(fid, int)]
                include_false = any(fid is False for fid in field)

                if non_null_ids and include_false:
                    return ['|', (field_name, 'in', non_null_ids), (field_name, '=', False)]
                elif non_null_ids:
                    return [(field_name, 'in', non_null_ids)]
                elif include_false:
                    return [(field_name, '=', False)]
            return None

        try:
            domain = [("display_in_project", "=", True)]
            if not project_id:
                return {
                    'status': 'false',
                    'error': 'project_id is required.'
                }

            try:
                project_id = int(project_id)
                domain.append(("project_id", "=", project_id))
            except (ValueError, TypeError):
                return {
                    'status': 'false',
                    'error': 'Invalid project_id format. Must be a valid integer.'
                }

            if user_ids:
                if isinstance(user_ids, list):
                    # Separate valid IDs and False/None
                    non_null_user_ids = [uid for uid in user_ids if isinstance(uid, int)]
                    include_unassigned = any(uid is False for uid in user_ids)

                    if non_null_user_ids and include_unassigned:
                        # Combine assigned users and unassigned tasks
                        domain += ['|', ('user_ids', 'in', non_null_user_ids), ('user_ids', '=', False)]
                    elif non_null_user_ids:
                        # Only assigned users
                        domain.append(('user_ids', 'in', non_null_user_ids))
                    elif include_unassigned:
                        # Only unassigned tasks
                        domain.append(('user_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid user_ids format. Must be a list of integers or False.'
                    }

            if tag_ids:
                if isinstance(tag_ids, list):
                    non_null_tag_ids = [tid for tid in tag_ids if isinstance(tid, int)]
                    include_untagged = any(tid is False for tid in tag_ids)

                    if non_null_tag_ids and include_untagged:
                        domain += ['|', ('tag_ids', 'in', non_null_tag_ids), ('tag_ids', '=', False)]
                    elif non_null_tag_ids:
                        domain.append(('tag_ids', 'in', non_null_tag_ids))
                    elif include_untagged:
                        domain.append(('tag_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid tag_ids format. Must be a list of integers or False.'
                    }

            if company_id is not None:
                try:
                    domain += process_field(company_id, 'company_id')
                except ValueError as e:
                    return {'status': 'false', 'error': str(e)}

            if milestone_id is not None:
                try:
                    domain += process_field(milestone_id, 'milestone_id')
                except ValueError as e:
                    return {'status': 'false', 'error': str(e)}

            stage_domain = [('project_ids', '=', project_id)] if project_id else []
            all_stages = request.env['project.task.type'].sudo().search(stage_domain)

            task_data = request.env['project.task'].sudo().read_group(
                domain=domain,
                fields=['stage_id'],
                groupby=['stage_id']
            )

            task_counts = {group['stage_id'][0]: group['stage_id_count'] for group in task_data}

            response = {
                'status': 'success',
                'data': [
                    {
                        'stage_id': stage.id,
                        'stage_name': stage.name,
                        'count': task_counts.get(stage.id, 0)
                    } for stage in all_stages
                ]
            }

            return response
        except Exception as query_error:
            return {
                'status': 'false',
                'error': str(query_error)
            }


class ProjectCountAPI(http.Controller):

    @http.route('/web/project/count', type='json', auth='user')
    def project_count(self, user_id=None, tag_ids=None, company_id=None, last_update_status=None):
        try:
            domain = [("is_internal_project", "=", False), ("is_fsm", "=", False)]

            if user_id:
                if isinstance(user_id, list):
                    if None in user_id:  # Check for None (unassigned projects)
                        user_id = [uid for uid in user_id if uid is not None]  # Filter out None
                        if user_id:
                            domain = ['|', ('user_id', 'in', user_id), ('user_id', '=', False)]
                        else:
                            domain.append(('user_id', '=', False))
                    else:
                        domain.append(('user_id', 'in', user_id))
                elif isinstance(user_id, str):
                    try:
                        user_ids = [int(uid.strip()) if uid.strip() != 'null' else None for uid in user_id.split(',')]
                        if None in user_ids:  # Check for None (unassigned projects)
                            user_ids = [uid for uid in user_ids if uid is not None]
                            if user_ids:
                                domain = ['|', ('user_id', 'in', user_ids), ('user_id', '=', False)]
                            else:
                                domain.append(('user_id', '=', False))
                        else:
                            domain.append(('user_id', 'in', user_ids))
                    except ValueError:
                        return {'status': 'false',
                                'error': 'Invalid user_id format. Must be a list of integers or a comma-separated string.'}
                else:
                    return {'status': 'false', 'error': 'Invalid user_id format. Must be a list or string.'}

            if tag_ids:
                if isinstance(tag_ids, list):
                    non_null_tag_ids = [tid for tid in tag_ids if isinstance(tid, int)]
                    include_untagged = any(tid is False for tid in tag_ids)

                    # If both non-null tag IDs and include_untagged are true, use the OR condition
                    if non_null_tag_ids and include_untagged:
                        domain += ['|', ('tag_ids', 'in', non_null_tag_ids), ('tag_ids', '=', False)]
                    elif non_null_tag_ids:
                        domain.append(('tag_ids', 'in', non_null_tag_ids))
                    elif include_untagged:
                        domain.append(('tag_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid tag_ids format. Must be a list of integers or False.'
                    }

            if company_id:
                if isinstance(company_id, list):
                    domain.append(('company_id', 'in', company_id))
                else:
                    return {'status': 'false', 'error': 'Invalid company_id format. Must be a list.'}

            if last_update_status:
                if isinstance(last_update_status, list):
                    domain.append(('last_update_status', 'in', last_update_status))
                else:
                    return {'status': 'false', 'error': 'Invalid last_update_status format. Must be a list.'}

            task_data = request.env['project.project'].sudo().read_group(
                domain=domain,
                fields=['stage_id'],
                groupby=['stage_id']
            )

            response_data = [
                {
                    'stage_id': group['stage_id'][0],
                    'stage_name': group['stage_id'][1],
                    'count': group['stage_id_count']
                } for group in task_data
            ]

            return {
                'status': 'success',
                'data': response_data
            }

        except Exception as query_error:
            message = str(query_error)
            return {
                'status': 'false',
                'error': message
            }


class ProjectTodoAPI(http.Controller):
    @http.route('/web/todo/count', type='json', auth='user')
    def todo_count(self, user_ids=None, tag_ids=None):
        try:
            # Get current user's personal stages
            current_user = request.env.user
            personal_stages = request.env['project.task.type'].sudo().search([
                ('user_id', '=', current_user.id)
            ])

            # Base domain that always applies
            domain = [
                ('project_id', '=', False),
                ('parent_id', '=', False),
                ('active', '=', True),
                ('state', 'in', (
                    '01_in_progress',
                    '02_changes_requested',
                    '03_approved',
                    '04_waiting_normal',
                    '1_done',
                    '1_canceled'
                ))
            ]

            # Helper function to safely convert and validate IDs
            def parse_id_list(ids, field_name):
                if not ids:
                    return []
                try:
                    return [int(id) for id in ids]
                except ValueError:
                    raise ValueError(
                        f'Invalid {field_name} format. Must be a list of integers.'
                    )

            # If no user_ids provided, use current user
            if not user_ids:
                domain.append(('user_ids', '=', current_user.id))
            else:
                # Add specified user conditions
                parsed_user_ids = parse_id_list(user_ids, 'user_ids')
                if len(parsed_user_ids) > 1:
                    domain.append('&')
                domain.extend(('user_ids', '=', uid) for uid in parsed_user_ids)

            # Add tag conditions if specified
            if tag_ids:
                parsed_tag_ids = parse_id_list(tag_ids, 'tag_ids')
                if len(parsed_tag_ids) > 1:
                    domain.append('&')
                domain.extend(('tag_ids', '=', tid) for tid in parsed_tag_ids)

            # Fetch task counts for each personal stage
            result = []
            for stage in personal_stages:
                stage_domain = domain + [('personal_stage_type_id', '=', stage.id)]
                count = request.env['project.task'].sudo().search_count(stage_domain)

                result.append({
                    'stage_id': stage.id,
                    'stage_name': stage.name,
                    'count': count
                })

            return {
                'status': 'success',
                'result': result
            }

        except ValueError as ve:
            return {
                'status': 'false',
                'error': str(ve)
            }
        except Exception as e:
            return {
                'status': 'false',
                'error': str(e)
            }


# ----------------------------------------------------------

from odoo.http import Controller, route, request


# class MenuAPIController(http.Controller):
#     @http.route('/web/get_user_menus', type='json', auth='user')
#     def get_user_menus(self):
#         try:
#             user = request.env.user
#             user_groups = user.groups_id.ids
#
#             # Define allowed top-level menu names
#             allowed_menu_names = ['CRM', 'Project', 'To-do', 'Attendances', 'Leave', 'Service Call', 'Contacts',
#                                   'Discuss']
#
#             # Explicitly exclude menus under Settings/Technical path
#             Menu = request.env['ir.ui.menu']
#
#             # Get top-level menus matching our list, but exclude those under Settings/Technical
#             top_menus = Menu.search([
#                 ('name', 'in', allowed_menu_names),
#                 '|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)
#             ])
#
#             if not top_menus:
#                 return {
#                     'user_groups': user_groups,
#                     'menus': []
#                 }
#
#             # Get all children of the allowed top menus
#             all_menu_ids = []
#             for menu in top_menus:
#                 all_menu_ids.append(menu.id)
#
#                 # Get all child menus using Odoo's domain operator
#                 child_menus = Menu.search([
#                     ('id', 'child_of', menu.id),
#                     ('id', '!=', menu.id),  # Exclude the parent itself
#                 ])
#                 all_menu_ids.extend(child_menus.ids)
#
#             # Check each menu's actual accessibility
#             accessible_menu_ids = []
#             for menu_id in all_menu_ids:
#                 menu = Menu.browse(menu_id)
#
#                 # Skip menus under Settings/Technical
#                 if 'Settings/Technical' in menu.complete_name:
#                     continue
#
#                 # Check group restrictions
#                 if menu.groups_id and not set(menu.groups_id.ids).intersection(set(user_groups)):
#                     continue
#
#                 # If menu has an action, verify model access
#                 if menu.action and menu.action._name == 'ir.actions.act_window' and menu.action.res_model:
#                     model_name = menu.action.res_model
#                     if model_name not in request.env:
#                         continue
#
#                     try:
#                         # Check read permission
#                         model = request.env[model_name]
#                         model.check_access_rights('read')
#                     except Exception:
#                         continue
#
#                 # Menu is accessible
#                 accessible_menu_ids.append(menu_id)
#
#             # Get menu data
#             if accessible_menu_ids:
#                 menus = Menu.search_read(
#                     [('id', 'in', accessible_menu_ids)],
#                     fields=['name', 'id', 'parent_id', 'child_id', 'action', 'sequence',
#                             'complete_name', 'web_icon', 'is_quick'],
#                     order='parent_path, sequence'
#                 )
#
#                 # Final filter to remove any Settings/Technical menus that might have slipped through
#                 menus = [menu for menu in menus if 'Settings/Technical' not in menu['complete_name']]
#             else:
#                 menus = []
#
#             return {
#                 'user_groups': user_groups,
#                 'menus': menus,
#             }
#
#         except Exception as e:
#             import logging
#             _logger = logging.getLogger(__name__)
#             _logger.error(f"Error in get_user_menus: {str(e)}")
#             return {
#                 'error': str(e),
#                 'menus': []
#             }

class MenuAPIController(http.Controller):
    @http.route('/web/get_user_menus', type='json', auth='user')
    def get_user_menus(self):
        import logging
        _logger = logging.getLogger(__name__)
        try:
            user = request.env.user
            user_groups = user.groups_id.ids
            Menu = request.env['ir.ui.menu']

            admin_group = request.env.ref('base.group_system').id
            is_admin = admin_group in user_groups

            allowed_menu_names = ['CRM', 'Project', 'To-do', 'Attendances', 'Leave', 'Service Call', 'Contacts',
                                  'Discuss']

            # Step 1: Get all menus visible by group
            visible_menus = Menu.search([
                '|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)
            ])

            # Step 2: Build parent-child tree
            def is_menu_accessible(menu):
                # Skip Settings/Technical menus for non-admin
                if not is_admin and 'Settings' in menu.complete_name:
                    return False

                if menu.groups_id and not set(menu.groups_id.ids).intersection(user_groups):
                    return False

                if menu.action and menu.action._name == 'ir.actions.act_window' and menu.action.res_model:
                    try:
                        request.env[menu.action.res_model].check_access_rights('read')
                    except Exception:
                        return False

                return True

            # Recursive tree walk with full access checks
            def collect_accessible_menu_tree(menus):
                accessible_ids = set()

                for menu in menus:
                    if is_menu_accessible(menu):
                        accessible_ids.add(menu.id)
                        # recursively check children
                        child_menus = menu.child_id
                        accessible_ids |= collect_accessible_menu_tree(child_menus)

                return accessible_ids

            # Step 3: Start from top menus (like root level ones matching names)
            top_menus = Menu.search([
                ('name', 'in', allowed_menu_names),
                ('parent_id', '=', False),
                '|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)
            ])

            accessible_menu_ids = collect_accessible_menu_tree(top_menus)

            # Step 4: Search only those menus
            menus = Menu.search_read(
                [('id', 'in', list(accessible_menu_ids))],
                fields=['name', 'id', 'parent_id', 'child_id', 'action', 'sequence',
                        'complete_name', 'web_icon', 'is_quick'],
                order='parent_path, sequence'
            )

            return {
                'user_groups': user_groups,
                'menus': menus
            }

        except Exception as e:
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error in get_user_menus: {str(e)}")
            return {'error': str(e), 'menus': []}


# class MenuAPIController(http.Controller):
#     @http.route('/web/get_user_menus', type='json', auth='user')
#     def get_user_menus(self):
#         try:
#             user = request.env.user
#             user_groups = user.groups_id.ids  # Get user's group IDs
#
#             # Fetch menus visible to the user's groups or globally accessible
#             menus = request.env['ir.ui.menu'].search_read(
#                 ['|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)],
#                 fields=['name', 'id', 'parent_id', 'child_id', 'action', 'sequence',
#                         'complete_name', 'web_icon', 'is_quick', 'is_for_mobile'],
#                 order='parent_path, sequence'
#             )
#
#             # Create a dictionary for faster parent lookups
#             menu_dict = {menu['id']: menu for menu in menus}
#             allowed_menus = ['CRM', 'Project', 'To-do', 'Attendances', 'Leave', 'Service Call', 'Contacts', 'Discuss']
#             filtered_menus = []
#
#             # Filter menus with proper parent checking
#             for menu in menus:
#                 # Include if it's an allowed top menu
#                 if menu['name'] in allowed_menus:
#                     filtered_menus.append(menu)
#                     continue
#
#                 # Include if it's a child of an allowed menu
#                 if menu['parent_id']:
#                     parent_id = menu['parent_id'][0]
#                     current_parent = menu_dict.get(parent_id)
#
#                     # Check parent chain until we find an allowed menu or reach the top
#                     while current_parent:
#                         if current_parent['name'] in allowed_menus:
#                             filtered_menus.append(menu)
#                             break
#                         if not current_parent.get('parent_id'):
#                             break
#                         parent_id = current_parent['parent_id'][0]
#                         current_parent = menu_dict.get(parent_id)
#
#             return {
#                 'user_groups': user_groups,
#                 'menus': filtered_menus,
#             }
#
#         except Exception as e:
#             return {
#                 'error': str(e),
#                 'menus': []
#             }


class AttendanceAPI(http.Controller):

    @http.route('/web/attendance/validate', type='json', auth='user')
    def validate_attendance(self, employee_id, check_in):
        check_in_date = fields.Datetime.from_string(check_in)
        user_tz = request.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        check_in_date = pytz.UTC.localize(check_in_date).astimezone(local_tz)

        attendance_count = request.env['hr.attendance'].sudo().search_count([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', check_in_date.replace(hour=0, minute=0, second=0, microsecond=0)),
            ('check_in', '<', check_in_date.replace(hour=23, minute=59, second=59, microsecond=999999))
        ])
        print(attendance_count)

        if attendance_count == 1:
            weekday = check_in_date.weekday()
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            resource_calendar = employee.resource_calendar_id
            if resource_calendar:
                for attendance in resource_calendar.attendance_ids:
                    if int(attendance.dayofweek) == weekday and attendance.day_period == 'morning':
                        work_from_time = attendance.hour_from
            else:
                return {'message': 'resource calender not found.'}

            allowed_minutes = int(
                request.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=0)
            )
            total_minutes = int(work_from_time * 60) + allowed_minutes
            allowed_time = f"{total_minutes // 60:02}:{total_minutes % 60:02}"
            check_in_time = check_in_date.strftime('%H:%M')

            notify_late = bool(
                request.env['ir.config_parameter'].sudo().get_param('hr_attendance.notification_late_day_in',
                                                                    default=False)
            )
            if notify_late and check_in_time > allowed_time:
                return {
                    'message': 'You are reporting late for work – your pay might be impacted.'
                }

        else:
            return {'message': 'Attendance validated successfully.'}
