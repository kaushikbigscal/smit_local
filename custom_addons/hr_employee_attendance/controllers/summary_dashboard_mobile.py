# from odoo import http
# from odoo.http import request
# from datetime import datetime
# import logging
# import pytz
#
# logger = logging.getLogger(__name__)
#
#
# class CustomApiController(http.Controller):
#
#     @http.route('/web/user_data', type='json', auth='user', csrf=False)
#     def handle_combined_api(self, date_start=None, date_end=None, user_id=None,
#                             assigned_by_me=False, assigned_to_me=False):
#         ist_tz = pytz.timezone('Asia/Kolkata')
#         current_user_id = request.env.uid
#
#         # Initialize date domain
#         date_domain = []
#
#         # Convert string flags to boolean if they came as strings
#         if isinstance(assigned_by_me, str):
#             assigned_by_me = assigned_by_me.lower() == 'true'
#         if isinstance(assigned_to_me, str):
#             assigned_to_me = assigned_to_me.lower() == 'true'
#
#         # Add logging for debugging
#         logger.info(f"API params: date_start={date_start}, date_end={date_end}, user_id={user_id}, "
#                     f"assigned_by_me={assigned_by_me}, assigned_to_me={assigned_to_me}, current_user={current_user_id}")
#
#         # Add date filters if provided
#         if date_start and date_end:
#             try:
#                 # Parse input dates
#                 start_date = datetime.strptime(date_start, '%Y-%m-%d')
#                 end_date = datetime.strptime(date_end, '%Y-%m-%d')
#
#                 # Create naive datetime objects with desired times
#                 start_naive = start_date.replace(hour=0, minute=0, second=0)
#                 end_naive = end_date.replace(hour=23, minute=59, second=59)
#
#                 # Properly localize to IST
#                 start_date_ist = ist_tz.localize(start_naive)
#                 end_date_ist = ist_tz.localize(end_naive)
#
#                 # Convert to UTC
#                 start_date_utc = start_date_ist.astimezone(pytz.UTC)
#                 end_date_utc = end_date_ist.astimezone(pytz.UTC)
#
#                 # Format for query
#                 start_date_query_utc = start_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#                 end_date_query_utc = end_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#
#                 date_domain = [
#                     ["create_date", ">=", start_date_query_utc],
#                     ["create_date", "<=", end_date_query_utc]
#                 ]
#
#                 logger.info(f"Date domain: {date_domain}")
#             except Exception as e:
#                 logger.error(f"Error processing date filters: {e}")
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
#                 logger.info(f"Fetching {category_name} with domain: {domain}")
#                 records = request.env[model].search_read(domain, fields)
#                 logger.info(f"Found {len(records)} {category_name}")
#                 response[category_name] = rename_fields(records, field_map)
#             except Exception as e:
#                 logger.error(f"Error fetching {category_name}: {e}")
#                 response[category_name] = []  # Return empty if no access
#
#         # Ensure we have valid user_id if provided
#         if user_id and isinstance(user_id, str) and user_id.isdigit():
#             user_id = int(user_id)
#
#         # Ensure we're not applying contradictory filters
#         if assigned_to_me and assigned_by_me:
#             logger.warning("Both assigned_to_me and assigned_by_me flags set. Using assigned_to_me logic.")
#             assigned_by_me = False  # assigned_to_me takes precedence
#
#         # Fetch tasks
#         if assigned_by_me:
#             # Find users that are not the current user
#             excluded_user_ids = request.env['res.users'].search([('id', '!=', current_user_id)]).ids
#
#             # Tasks assigned by me to others - records I created and assigned to someone else
#             task_domain = [
#                               ["is_fsm", "=", False],
#                               ('create_uid', '=', current_user_id),  # I created it
#                               ('user_ids', '!=', False),  # It has assignees
#                               ('user_ids', 'not in', [current_user_id])  # I'm not in the assignees
#                           ] + date_domain
#
#             logger.info(f"Task domain for assigned_by_me: {task_domain}")
#         elif assigned_to_me:
#             # Tasks assigned to me - records where I am an assignee
#             task_domain = [
#                               ["is_fsm", "=", False],
#                               ('user_ids', 'in', [current_user_id])  # I am in the assignees
#                           ] + date_domain
#
#             logger.info(f"Task domain for assigned_to_me: {task_domain}")
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_ids", "in", [user_id]]]
#
#             task_domain = [["is_fsm", "=", False]] + user_domain + date_domain
#
#             logger.info(f"Task domain for regular filtering: {task_domain}")
#
#         fetch_model_data(
#             'project.task',
#             task_domain,
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'tasks'
#         )
#
#         # Fetch leads
#         if assigned_by_me:
#             # Leads assigned by me to others (for CRM models user_id is a many2one field)
#             lead_domain = [
#                               ["type", "=", "lead"],
#                               ('create_uid', '=', current_user_id),  # I created it
#                               ('user_id', '!=', current_user_id),  # It's assigned to someone else
#                               ('user_id', '!=', False)  # It's actually assigned
#                           ] + date_domain
#         elif assigned_to_me:
#             # Leads assigned to me
#             lead_domain = [
#                               ["type", "=", "lead"],
#                               ('user_id', '=', current_user_id)  # It's assigned to me
#                           ] + date_domain
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_id", "=", user_id]]
#
#             lead_domain = [["type", "=", "lead"]] + user_domain + date_domain
#
#         fetch_model_data(
#             'crm.lead',
#             lead_domain,
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'leads'
#         )
#
#         # Fetch service calls
#         if assigned_by_me:
#             # Service calls assigned by me to others
#             service_call_domain = [
#                                       ["is_fsm", "=", True],
#                                       ('create_uid', '=', current_user_id),  # I created it
#                                       ('user_ids', '!=', False),  # It has assignees
#                                       ('user_ids', 'not in', [current_user_id])  # I'm not in the assignees
#                                   ] + date_domain
#         elif assigned_to_me:
#             # Service calls assigned to me
#             service_call_domain = [
#                                       ["is_fsm", "=", True],
#                                       ('user_ids', 'in', [current_user_id])  # I am in the assignees
#                                   ] + date_domain
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_ids", "in", [user_id]]]
#
#             service_call_domain = [["is_fsm", "=", True]] + user_domain + date_domain
#
#         fetch_model_data(
#             'project.task',
#             service_call_domain,
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'service_calls'
#         )
#
#         # Fetch todo tasks
#         if assigned_by_me:
#             # Todo tasks assigned by me to others
#             todo_task_domain = [
#                                    ["project_id", "=", False],
#                                    ["parent_id", "=", False],
#                                    ('create_uid', '=', current_user_id),  # I created it
#                                    ('user_ids', '!=', False),  # It has assignees
#                                    ('user_ids', 'not in', [current_user_id])  # I'm not in the assignees
#                                ] + date_domain
#         elif assigned_to_me:
#             # Todo tasks assigned to me
#             todo_task_domain = [
#                                    ["project_id", "=", False],
#                                    ["parent_id", "=", False],
#                                    ('user_ids', 'in', [current_user_id])  # I am in the assignees
#                                ] + date_domain
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_ids", "in", [user_id]]]
#
#             todo_task_domain = [["project_id", "=", False], ["parent_id", "=", False]] + user_domain + date_domain
#
#         fetch_model_data(
#             'project.task',
#             todo_task_domain,
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'todo_tasks'
#         )
#
#         # Fetch opportunities
#         if assigned_by_me:
#             # Opportunities assigned by me to others
#             opportunity_domain = [
#                                      ["type", "=", "opportunity"],
#                                      ["active", "=", True],
#                                      ('create_uid', '=', current_user_id),  # I created it
#                                      ('user_id', '!=', current_user_id),  # It's assigned to someone else
#                                      ('user_id', '!=', False)  # It's actually assigned
#                                  ] + date_domain
#         elif assigned_to_me:
#             # Opportunities assigned to me
#             opportunity_domain = [
#                                      ["type", "=", "opportunity"],
#                                      ["active", "=", True],
#                                      ('user_id', '=', current_user_id)  # It's assigned to me
#                                  ] + date_domain
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_id", "=", user_id]]
#
#             opportunity_domain = [["type", "=", "opportunity"], ["active", "=", True]] + user_domain + date_domain
#
#         fetch_model_data(
#             'crm.lead',
#             opportunity_domain,
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'opportunities'
#         )
#
#         # Fetch projects
#         if assigned_by_me:
#             # Projects assigned by me to others
#             project_domain = [
#                                  ['is_internal_project', '=', False],
#                                  ('create_uid', '=', current_user_id),  # I created it
#                                  ('user_id', '!=', current_user_id),  # It's assigned to someone else
#                                  ('user_id', '!=', False)  # It's actually assigned
#                              ] + date_domain
#         elif assigned_to_me:
#             # Projects assigned to me
#             project_domain = [
#                                  ['is_internal_project', '=', False],
#                                  ('user_id', '=', current_user_id)  # It's assigned to me
#                              ] + date_domain
#         else:
#             # Filter by specific user_id if provided, otherwise return all
#             user_domain = []
#             if user_id:
#                 user_domain = [["user_id", "=", user_id]]
#
#             project_domain = [['is_internal_project', '=', False]] + user_domain + date_domain
#
#         fetch_model_data(
#             'project.project',
#             project_domain,
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
from odoo import http
from odoo.http import request
from datetime import datetime
import logging
import pytz

logger = logging.getLogger(__name__)


class CustomApiController(http.Controller):

    @http.route('/web/user_data', type='json', auth='user', csrf=False)
    def handle_combined_api(self, date_start=None, date_end=None, user_id=None,
                            assigned_by_me=False, assigned_to_me=False):
        ist_tz = pytz.timezone('Asia/Kolkata')
        current_user_id = request.env.uid

        # Initialize date domain
        date_domain = []

        # Convert string flags to boolean if they came as strings
        if isinstance(assigned_by_me, str):
            assigned_by_me = assigned_by_me.lower() == 'true'
        if isinstance(assigned_to_me, str):
            assigned_to_me = assigned_to_me.lower() == 'true'

        # Convert user_id to integer if it's a string
        if user_id and isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)

        # Add logging for debugging
        logger.info(f"API params: date_start={date_start}, date_end={date_end}, user_id={user_id}, "
                    f"assigned_by_me={assigned_by_me}, assigned_to_me={assigned_to_me}, current_user={current_user_id}")

        # Add date filters if provided
        if date_start and date_end:
            try:
                # Parse input dates
                start_date = datetime.strptime(date_start, '%Y-%m-%d')
                end_date = datetime.strptime(date_end, '%Y-%m-%d')

                # Create naive datetime objects with desired times
                start_naive = start_date.replace(hour=0, minute=0, second=0)
                end_naive = end_date.replace(hour=23, minute=59, second=59)

                # Properly localize to IST
                start_date_ist = ist_tz.localize(start_naive)
                end_date_ist = ist_tz.localize(end_naive)

                # Convert to UTC
                start_date_utc = start_date_ist.astimezone(pytz.UTC)
                end_date_utc = end_date_ist.astimezone(pytz.UTC)

                # Format for query
                start_date_query_utc = start_date_utc.strftime('%Y-%m-%d %H:%M:%S')
                end_date_query_utc = end_date_utc.strftime('%Y-%m-%d %H:%M:%S')

                date_domain = [
                    ["create_date", ">=", start_date_query_utc],
                    ["create_date", "<=", end_date_query_utc]
                ]

                logger.info(f"Date domain: {date_domain}")
            except Exception as e:
                logger.error(f"Error processing date filters: {e}")

        def rename_fields(records, field_map):
            for record in records:
                for old_field, new_field in field_map.items():
                    if old_field in record:
                        record[new_field] = record.pop(old_field)
            return records

        response = {}

        def fetch_model_data(model, domain, fields, field_map, category_name):
            try:
                logger.info(f"Fetching {category_name} with domain: {domain}")
                records = request.env[model].search_read(domain, fields)
                logger.info(f"Found {len(records)} {category_name}")
                response[category_name] = rename_fields(records, field_map)
            except Exception as e:
                logger.error(f"Error fetching {category_name}: {e}")
                response[category_name] = []  # Return empty if no access

        # Ensure we're not applying contradictory filters
        if assigned_to_me and assigned_by_me:
            logger.warning("Both assigned_to_me and assigned_by_me flags set. Using assigned_to_me logic.")
            assigned_by_me = False  # assigned_to_me takes precedence

        # Fetch tasks
        if assigned_by_me:
            # Tasks assigned by me to others
            task_domain = [
                              ["is_fsm", "=", False],
                              ('create_uid', '=', current_user_id),  # I created it
                              ('user_ids', '!=', False),  # It has assignees
                          ] + date_domain

            # Add user_id filter if provided
            if user_id:
                task_domain.append(('user_ids', 'in', [user_id]))  # Assigned to specific user
            else:
                task_domain.append(('user_ids', 'not in', [current_user_id]))  # Not assigned to me

            logger.info(f"Task domain for assigned_by_me: {task_domain}")
        elif assigned_to_me:
            # Tasks assigned to me - this takes precedence over user_id
            task_domain = [
                              ["is_fsm", "=", False],
                              ('user_ids', 'in', [current_user_id])  # I am in the assignees
                          ] + date_domain

            logger.info(f"Task domain for assigned_to_me: {task_domain}")
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_ids", "in", [user_id]]]

            task_domain = [["is_fsm", "=", False]] + user_domain + date_domain

            logger.info(f"Task domain for regular filtering: {task_domain}")

        fetch_model_data(
            'project.task',
            task_domain,
            ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
            {'state': 'status'},
            'tasks'
        )

        # Fetch leads
        if assigned_by_me:
            # Leads assigned by me to others
            lead_domain = [
                              ["type", "=", "lead"],
                              ('create_uid', '=', current_user_id),  # I created it
                              ('user_id', '!=', False)  # It's actually assigned
                          ] + date_domain

            # Add user_id filter if provided
            if user_id:
                lead_domain.append(('user_id', '=', user_id))  # Assigned to specific user
            else:
                lead_domain.append(('user_id', '!=', current_user_id))  # Not assigned to me

        elif assigned_to_me:
            # Leads assigned to me - this takes precedence over user_id
            lead_domain = [
                              ["type", "=", "lead"],
                              ('user_id', '=', current_user_id)  # It's assigned to me
                          ] + date_domain
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_id", "=", user_id]]

            lead_domain = [["type", "=", "lead"]] + user_domain + date_domain

        fetch_model_data(
            'crm.lead',
            lead_domain,
            ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
            {'stage_id': 'status'},
            'leads'
        )

        # Fetch service calls
        if assigned_by_me:
            # Service calls assigned by me to others
            service_call_domain = [
                                      ["is_fsm", "=", True],
                                      ('create_uid', '=', current_user_id),  # I created it
                                      ('user_ids', '!=', False),  # It has assignees
                                  ] + date_domain

            # Add user_id filter if provided
            if user_id:
                service_call_domain.append(('user_ids', 'in', [user_id]))  # Assigned to specific user
            else:
                service_call_domain.append(('user_ids', 'not in', [current_user_id]))  # Not assigned to me

        elif assigned_to_me:
            # Service calls assigned to me - this takes precedence over user_id
            service_call_domain = [
                                      ["is_fsm", "=", True],
                                      ('user_ids', 'in', [current_user_id])  # I am in the assignees
                                  ] + date_domain
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_ids", "in", [user_id]]]

            service_call_domain = [["is_fsm", "=", True]] + user_domain + date_domain

        fetch_model_data(
            'project.task',
            service_call_domain,
            ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
            {'stage_id': 'status'},
            'service_calls'
        )

        # Fetch todo tasks
        if assigned_by_me:
            # Todo tasks assigned by me to others
            todo_task_domain = [
                                   ["project_id", "=", False],
                                   ["parent_id", "=", False],
                                   ('create_uid', '=', current_user_id),  # I created it
                                   ('user_ids', '!=', False),  # It has assignees
                               ] + date_domain

            # Add user_id filter if provided
            if user_id:
                todo_task_domain.append(('user_ids', 'in', [user_id]))  # Assigned to specific user
            else:
                todo_task_domain.append(('user_ids', 'not in', [current_user_id]))  # Not assigned to me

        elif assigned_to_me:
            # Todo tasks assigned to me - this takes precedence over user_id
            todo_task_domain = [
                                   ["project_id", "=", False],
                                   ["parent_id", "=", False],
                                   ('user_ids', 'in', [current_user_id])  # I am in the assignees
                               ] + date_domain
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_ids", "in", [user_id]]]

            todo_task_domain = [["project_id", "=", False], ["parent_id", "=", False]] + user_domain + date_domain

        fetch_model_data(
            'project.task',
            todo_task_domain,
            ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
            {'state': 'status'},
            'todo_tasks'
        )

        # Fetch opportunities
        if assigned_by_me:
            # Opportunities assigned by me to others
            opportunity_domain = [
                                     ["type", "=", "opportunity"],
                                     ["active", "=", True],
                                     ('create_uid', '=', current_user_id),  # I created it
                                     ('user_id', '!=', False)  # It's actually assigned
                                 ] + date_domain

            # Add user_id filter if provided
            if user_id:
                opportunity_domain.append(('user_id', '=', user_id))  # Assigned to specific user
            else:
                opportunity_domain.append(('user_id', '!=', current_user_id))  # Not assigned to me

        elif assigned_to_me:
            # Opportunities assigned to me - this takes precedence over user_id
            opportunity_domain = [
                                     ["type", "=", "opportunity"],
                                     ["active", "=", True],
                                     ('user_id', '=', current_user_id)  # It's assigned to me
                                 ] + date_domain
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_id", "=", user_id]]

            opportunity_domain = [["type", "=", "opportunity"], ["active", "=", True]] + user_domain + date_domain

        fetch_model_data(
            'crm.lead',
            opportunity_domain,
            ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
            {'stage_id': 'status'},
            'opportunities'
        )

        # Fetch projects
        if assigned_by_me:
            # Projects assigned by me to others
            project_domain = [
                                 ['is_internal_project', '=', False],
                                 ('create_uid', '=', current_user_id),  # I created it
                                 ('user_id', '!=', False)  # It's actually assigned
                             ] + date_domain

            # Add user_id filter if provided
            if user_id:
                project_domain.append(('user_id', '=', user_id))  # Assigned to specific user
            else:
                project_domain.append(('user_id', '!=', current_user_id))  # Not assigned to me

        elif assigned_to_me:
            # Projects assigned to me - this takes precedence over user_id
            project_domain = [
                                 ['is_internal_project', '=', False],
                                 ('user_id', '=', current_user_id)  # It's assigned to me
                             ] + date_domain
        else:
            # Filter by specific user_id if provided, otherwise return all
            user_domain = []
            if user_id:
                user_domain = [["user_id", "=", user_id]]

            project_domain = [['is_internal_project', '=', False]] + user_domain + date_domain

        fetch_model_data(
            'project.project',
            project_domain,
            ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
            {'stage_id': 'status'},
            'projects'
        )

        # Process user_ids and tag_ids for records
        for category in ['tasks', 'leads', 'service_calls', 'todo_tasks', 'opportunities', 'projects']:
            for record in response.get(category, []):
                if 'user_ids' in record and isinstance(record['user_ids'], list):
                    users = request.env['res.users'].browse(record['user_ids'])
                    record['user_ids'] = [{'id': user.id, 'name': user.name} for user in users]

                if category in ['tasks', 'todo_tasks', 'projects', 'service_calls']:
                    if 'tag_ids' in record and isinstance(record['tag_ids'], list):
                        tags = request.env['project.tags'].browse(record['tag_ids'])
                        record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]

                elif category in ['leads', 'opportunities']:
                    if 'tag_ids' in record and isinstance(record['tag_ids'], list):
                        tags = request.env['crm.tag'].browse(record['tag_ids'])
                        record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]

        return {
            'status': 'success',
            'result': response,
        }
