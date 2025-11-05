from collections import defaultdict
from datetime import datetime, timedelta, date
from odoo import http
from odoo.http import request
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class ProjectFilter(http.Controller):
    """The ProjectFilter class provides the filter option to the js.
    When applying the filter returns the corresponding data."""


    @http.route('/get/project_template', type='json', auth='user')
    def get_project_template(self):
        """Fetch project templates where the current user is assigned to non-blocked tasks."""
        try:
            user_id = request.env.user.id
            lang = request.env.lang or 'en_US'

            # Check if the logged-in user is an admin
            is_admin = request.env.user.has_group('base.group_system')

            # Admins can see all templates (no filtering)
            if is_admin:
                query_admin = """
                    SELECT DISTINCT pp.x_template
                    FROM project_project pp
                    WHERE pp.active = true
                      AND pp.is_fsm = false
                      AND pp.x_template IS NOT NULL
                    ORDER BY pp.x_template;
                """
                request.env.cr.execute(query_admin)
                result = request.env.cr.fetchall()
            else:
                # Check if the user is a project manager for a project (assigned in user_id field)
                query_project_manager = """
                    SELECT DISTINCT pp.x_template
                    FROM project_project pp
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.x_template IS NOT NULL
                      AND pp.user_id = %s  -- Check if the logged-in user is the project manager
                    ORDER BY pp.x_template;
                """
                request.env.cr.execute(query_project_manager, (user_id,))
                result = request.env.cr.fetchall()

                # If no results for project manager, check for normal user tasks
                if not result:
                    query_normal_user = """
                        SELECT DISTINCT pp.x_template
                        FROM project_project pp
                        WHERE pp.active = TRUE
                          AND pp.is_fsm = FALSE
                          AND pp.x_template IS NOT NULL
                          AND pp.id IN (
                              SELECT pt.project_id
                              FROM project_task pt
                              JOIN project_task_user_rel rel ON pt.id = rel.task_id
                              WHERE rel.user_id = %s
                                AND pt.active = TRUE
                                AND pt.state NOT IN ('1_done', '1_canceled', '04_waiting_normal')  -- Exclude done/canceled tasks
                          )
                        ORDER BY pp.x_template;
                    """
                    request.env.cr.execute(query_normal_user, (user_id,))
                    result = request.env.cr.fetchall()

            # If no templates are found, return an empty list
            if not result:
                return []

            # Format the result list
            template_list = []
            for row in result:
                if row[0]:
                    template_list.append({
                        'id': row[0],
                        'name': row[0]
                    })

            return template_list

        except Exception as e:
            _logger.error(f"Error fetching project templates: {e}", exc_info=True)
            return []

    @http.route('/get/departments', auth='public', type='json')
    def get_departments(self):
        try:
            lang = request.env.lang or 'en_US'
            user_id = request.env.user.id

            # True admin check
            is_admin = request.env.user.has_group('base.group_system')

            # Initialize query parameters with language code
            params = [lang]

            if is_admin:
                # Admins can see all departments linked to active, non-FSM projects
                query = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                    ORDER BY name;
                """
            else:
                # First: check if the user is a project manager (user_id in project)
                query_pm = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.user_id = %s
                    ORDER BY name;
                """
                request.env.cr.execute(query_pm, (lang, user_id))
                result = request.env.cr.fetchall()

                if result:
                    return [{'id': dept_id, 'name': dept_name} for dept_id, dept_name in result if dept_name]

                # If not a PM, fallback to normal user logic
                query = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    JOIN project_task pt ON pt.project_id = pp.id
                    JOIN project_task_user_rel rel ON rel.task_id = pt.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND rel.user_id = %s
                      AND pt.state NOT IN ('1_done', '1_canceled', '04_waiting_normal')
                      AND EXISTS (
                          SELECT 1
                          FROM project_task pt_sub
                          JOIN project_task_user_rel rel_sub ON rel_sub.task_id = pt_sub.id
                          WHERE pt_sub.project_id = pp.id
                            AND rel_sub.user_id = %s
                            AND pt_sub.state != '04_waiting_normal'
                      )
                    ORDER BY name;
                """
                params += [user_id, user_id]

            # Execute final query
            request.env.cr.execute(query, tuple(params))
            result = request.env.cr.fetchall()

            departments = [{'id': dept_id, 'name': dept_name} for dept_id, dept_name in result if dept_name]
            return departments

        except Exception as e:
            _logger.error(f"Error fetching departments: {e}", exc_info=True)
            return []

    @http.route('/get/tiles/data', auth='public', type='json')
    def get_tiles_data(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            user_id = user.id
            is_admin = user.has_group('project.group_project_manager')
            today = fields.Date.today()
            yesterday = today - timedelta(days=1)
            tomorrow = today + timedelta(days=1)

            base_domain = [
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
                ('active', '=', True),
            ]

            # Department filter
            if department_id:
                department_ids = (
                    [int(d) for d in department_id] if isinstance(department_id, list)
                    else [int(d) for d in str(department_id).split(",") if d.isdigit()]
                )
                if department_ids:
                    base_domain.append(('x_department', 'in', department_ids))

            # Template filter
            if x_template:
                templates = x_template if isinstance(x_template, list) else x_template.split(",")
                if templates:
                    if len(templates) == 1:
                        base_domain.append(('x_template', '=', templates[0]))
                    else:
                        base_domain.extend(['|'] * (len(templates) - 1))
                        base_domain.extend([('x_template', '=', t) for t in templates])

            # Date range filter
            if start_date and end_date:
                base_domain.extend([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ])

            # Determine user role
            pm_project_ids = request.env['project.project'].search([('user_id', '=', user_id)]).ids
            user_task_projects = request.env['project.task'].search([
                ('user_ids', 'in', [user_id]),
                ('active', '=', True),
                ('depend_on_ids', '=', False),
                ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']),
            ]).mapped('project_id').ids

            combined_project_ids = list(set(pm_project_ids + user_task_projects))
            # Apply access filter for non-admins
            if not is_admin:
                if combined_project_ids:
                    base_domain.append(('id', 'in', combined_project_ids))
                else:
                    base_domain.append(('id', '=', 0))  # No access

            all_projects = request.env['project.project'].search(base_domain)
            all_project_ids = all_projects.ids

            # Task domain
            task_domain = [
                ('project_id', 'in', all_project_ids),
                ('active', '=', True),
                ('depend_on_ids', '=', False),  # Only non-blocked
            ]

            # Regular users: only see their own tasks
            is_project_manager = bool(pm_project_ids)
            is_regular_user = not is_admin and not is_project_manager

            if is_regular_user:
                task_domain.append(('user_ids', 'in', [user_id]))
                task_domain.append(('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']))

            tasks = request.env['project.task'].search(task_domain)

            # Initialize stats
            stats = {
                'total_projects': 0,
                'active_projects': 0,
                'running_projects': 0,
                'done_projects': 0,
                'canceled_projects': 0,
                'expired_projects': 0,
                'expired_yesterday': 0,
                'expired_today': 0,
                'will_expire_tomorrow': 0,
                'total_tasks': 0,
                'running_tasks': 0,
                'done_tasks': 0,
                'canceled_tasks': 0,
                'expired_tasks': 0,
                'expired_yesterday_tasks': 0,
                'expired_today_tasks': 0,
                'will_expire_tomorrow_tasks': 0,
                'has_project_admin_rights': is_admin,
            }

            for project in all_projects:
                proj_date = project.date
                stage = project.stage_id.name if project.stage_id else ''

                if stage == 'Done':
                    stats['done_projects'] += 1
                elif stage == 'Canceled':
                    stats['canceled_projects'] += 1
                else:
                    stats['active_projects'] += 1
                    if stage == 'In Progress':
                        stats['running_projects'] += 1

                    if proj_date:
                        if proj_date < today:
                            stats['expired_projects'] += 1
                        if proj_date == yesterday:
                            stats['expired_yesterday'] += 1
                        if proj_date == today:
                            stats['expired_today'] += 1
                        if proj_date == tomorrow:
                            stats['will_expire_tomorrow'] += 1

            for task in tasks:
                state = task.state
                if task.depend_on_ids:
                    continue
                if state in ['01_in_progress', '02_changes_requested', '03_approved']:
                    stats['running_tasks'] += 1
                elif state == '1_done':
                    stats['done_tasks'] += 1
                elif state == '1_canceled':
                    stats['canceled_tasks'] += 1

                project = task.project_id
                if not project or project.stage_id.name in ['Done', 'Canceled']:
                    continue

                proj_date = project.date
                if proj_date:
                    if state == '1_done' or state == '1_canceled':
                        continue
                    if proj_date < today:
                        stats['expired_tasks'] += 1
                    if proj_date == yesterday:
                        stats['expired_yesterday_tasks'] += 1
                    if proj_date == today:
                        stats['expired_today_tasks'] += 1
                    if proj_date == tomorrow:
                        stats['will_expire_tomorrow_tasks'] += 1

            stats['total_projects'] = len(all_projects)
            stats['total_tasks'] = len(tasks)

            return stats

        except Exception as e:
            _logger.exception("Error in get_tiles_data")
            return {'error': f"An error occurred: {str(e)}"}


    @http.route('/project/task/by_employee', auth='user', type='json')
    def get_task_by_employee(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            is_admin = user.has_group('base.group_system')

            # Base project domain
            project_domain = [
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
                ('active', '=', True),
            ]

            if department_id:
                dept_ids = [int(d) for d in department_id] if isinstance(department_id, list) else \
                    [int(d) for d in str(department_id).split(',') if d.isdigit()]
                if dept_ids:
                    project_domain.append(('x_department', 'in', dept_ids))

            if x_template:
                templates = x_template if isinstance(x_template, list) else str(x_template).split(',')
                if len(templates) == 1:
                    project_domain.append(('x_template', '=', templates[0]))
                else:
                    template_domain = ['|'] * (len(templates) - 1)
                    for t in templates:
                        template_domain.append(('x_template', '=', t))
                    project_domain.extend(template_domain)

            if start_date and end_date:
                project_domain += [('date', '>=', start_date), ('date', '<=', end_date)]

            all_projects = request.env['project.project'].search(project_domain)
            if not all_projects:
                return {'labels': [], 'data': [], 'colors': []}

            # Task domain
            task_domain = [
                ('project_id', 'in', all_projects.ids),
                ('depend_on_ids', '=', False),
                ('active', '=', True),
            ]

            if is_admin:
                # Admin sees everything, including done and canceled
                pass
            else:
                # Identify PM-managed projects
                managed_projects = all_projects.filtered(lambda p: p.user_id.id == user.id)
                if managed_projects:
                    # PM sees all tasks (including done/canceled) in their projects
                    task_domain[0] = ('project_id', 'in', managed_projects.ids)
                else:
                    # Regular user: only see own tasks, excluding done/canceled
                    task_domain.append(('user_ids', 'in', [user.id]))
                    task_domain.append(('state', 'not in', ['1_done', '1_canceled']))

            tasks = request.env['project.task'].search(task_domain)
            if not tasks:
                return {'labels': [], 'data': [], 'colors': []}

            # Count tasks by assigned user
            user_task_map = {}
            for task in tasks:
                for assigned_user in task.user_ids:
                    # Regular user: skip others
                    if not is_admin and not managed_projects and assigned_user.id != user.id:
                        continue
                    user_task_map[assigned_user] = user_task_map.get(assigned_user, 0) + 1

            sorted_users = sorted(user_task_map.items(), key=lambda x: x[1], reverse=True)[:10]
            labels = [u.name for u, _ in sorted_users]
            data = [count for _, count in sorted_users]
            colors = [
                         '#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22',
                         '#e74c3c', '#1abc9c', '#34495e', '#95a5a6', '#16a085'
                     ][:len(labels)]

            return {'labels': labels, 'data': data, 'colors': colors}

        except Exception as e:
            _logger.error(f"[get_task_by_employee] Error: {e}")
            return {'labels': [], 'data': [], 'colors': []}

    @http.route('/project/task/by_tags', auth='user', type='json')
    def get_task_by_tags(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            is_admin = user.has_group('base.group_system')

            # Base project domain
            project_domain = [
                ('active', '=', True),
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
            ]

            if department_id:
                dept_ids = [int(d) for d in department_id] if isinstance(department_id, list) else \
                    [int(d) for d in str(department_id).split(',') if d.isdigit()]
                if dept_ids:
                    project_domain.append(('x_department', 'in', dept_ids))

            if x_template:
                templates = x_template if isinstance(x_template, list) else str(x_template).split(',')
                if len(templates) == 1:
                    project_domain.append(('x_template', '=', templates[0]))
                else:
                    template_domain = ['|'] * (len(templates) - 1)
                    for t in templates:
                        template_domain.append(('x_template', '=', t))
                    project_domain.extend(template_domain)

            if start_date and end_date:
                project_domain += [
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                ]

            all_projects = request.env['project.project'].search(project_domain)
            if not all_projects:
                return {'labels': [], 'data': [], 'colors': []}

            # Determine visible projects and task domain
            managed_projects = all_projects.filtered(lambda p: p.user_id.id == user.id)
            task_domain = [
                ('active', '=', True),
                ('depend_on_ids', '=', False),
            ]

            if is_admin:
                task_domain.append(('project_id', 'in', all_projects.ids))

            elif managed_projects:
                # Project Manager: tasks from managed projects + tasks assigned to them
                task_domain.append('|')
                task_domain += [
                    ('project_id', 'in', managed_projects.ids),
                    ('user_ids', 'in', [user.id]),
                ]
            else:
                # Normal user
                task_domain += [
                    ('project_id', 'in', all_projects.ids),
                    ('user_ids', 'in', [user.id]),
                    ('state', 'not in', ['1_done', '1_canceled']),
                ]

            tasks = request.env['project.task'].search(task_domain)
            if not tasks:
                return {'labels': [], 'data': [], 'colors': []}

            # Tag aggregation
            query = '''
                SELECT
                    COALESCE(tag.name->>%s, tag.name->>'en_US') as tag_name,
                    COUNT(DISTINCT task.id) as count
                FROM
                    project_task task
                JOIN
                    project_tags_project_task_rel rel ON task.id = rel.project_task_id
                JOIN
                    project_tags tag ON rel.project_tags_id = tag.id
                WHERE
                    task.id IN %s
                GROUP BY
                    tag_name
                ORDER BY
                    count DESC
                LIMIT 10
            '''
            lang = request.env.lang or 'en_US'
            request.env.cr.execute(query, (lang, tuple(tasks.ids)))
            tag_counts = request.env.cr.fetchall()

            labels = [row[0] for row in tag_counts if row[0]]
            data = [row[1] for row in tag_counts if row[0]]
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                      '#FF9F40', '#8B0000', '#2E8B57', '#8A2BE2', '#00CED1'][:len(labels)]

            return {
                'labels': labels,
                'data': data,
                'colors': colors,
            }

        except Exception as e:
            _logger.error(f"[get_task_by_tags] Error: {e}")
            return {'labels': [], 'data': [], 'colors': []}

    # Summary Dashboard By Company Level

    @http.route('/get/companies', auth='public', type='json')
    def get_companies(self):
        companies = request.env['res.company'].search([])
        return [{
            'id': company.id,
            'name': company.name
        } for company in companies]


    @http.route('/get/departments/by_company', auth='user', type='json')
    def get_departments_by_company(self, company_id=None):
        try:
            if not company_id:
                return []

            company_id = int(company_id)
            user = request.env.user
            has_project_admin_rights = user.has_group('project.group_project_manager')

            if has_project_admin_rights:
                # Admin: return all root departments in the company
                departments = request.env['hr.department'].search([
                    ('company_id', '=', company_id),
                    ('parent_id', '=', False)
                ])
            else:
                # Regular user: return only departments from projects where the user has assigned tasks
                assigned_project_ids = request.env['project.task'].search([
                    ('user_ids', 'in', [user.id]),
                    ('project_id.company_id', '=', company_id),
                    ('active', '=', True)
                ]).mapped('project_id')

                departments = assigned_project_ids.mapped('x_department').filtered(lambda d: d.parent_id is False)

            return [{
                'id': dept.id,
                'name': dept.name
            } for dept in departments]

        except Exception as e:
            _logger.error("Error fetching departments: %s", e)
            return []

    @http.route('/get/sub_departments', auth='public', type='json')
    def get_sub_departments(self, department_id):
        """Fetch sub-departments for a given department."""
        sub_departments = request.env['hr.department'].search([
            ('parent_id', '=', int(department_id))  # Assuming 'parent_id' is the field linking subdepartments to
            # their parent
        ])
        return [{
            'id': sub_dept.id,
            'name': sub_dept.name
        } for sub_dept in sub_departments]

    @http.route('/get/departments/used', auth='public', type='json')
    def get_used_departments(self):
        """Fetch only departments that are used in projects."""
        try:
            # Get departments that are used in projects
            query = """
                SELECT DISTINCT d.id, d.name
                FROM hr_department d
                JOIN project_project p ON p.x_department = d.id
                WHERE p.is_project_template = False
                ORDER BY d.name
            """
            request.env.cr.execute(query)
            departments = request.env.cr.dictfetchall()

            return [{
                'id': dept['id'],
                'name': dept['name']
            } for dept in departments]
        except Exception as e:
            _logger.error("Error fetching used departments: %s", str(e))
            return []
