# this code edited by satyam
from datetime import datetime, timedelta, date
from odoo import http
from odoo.http import request
from odoo import api, fields
import pytz
import logging

_logger = logging.getLogger(__name__)


class ProjectFilter(http.Controller):
    @http.route('/calls/filter', auth='public', type='json')
    def project_filter(self):
        project_list = []
        employee_list = []
        project_ids = request.env['project.task'].search([])
        employee_ids = request.env['hr.employee'].search([])
        # getting partner data
        for employee_id in employee_ids:
            dic = {'name': employee_id.name,
                   'id': employee_id.id}
            employee_list.append(dic)

        for project_id in project_ids:
            dic = {'name': project_id.name,
                   'id': project_id.id}
            project_list.append(dic)

        return [project_list, employee_list]

    @http.route('/calls/filter-apply', auth='public', type='json')
    def project_filter_apply(self, **kw):
        data = kw['data']
        # checking the employee selected or not
        if data['employee'] == 'null':
            emp_selected = [employee.id for employee in
                            request.env['hr.employee'].search([])]
        else:
            emp_selected = [int(data['employee'])]
        start_date = data['start_date']
        end_date = data['end_date']
        # checking the dates are selected or not
        if start_date != 'null' and end_date != 'null':
            start_date = datetime.datetime.strptime(start_date,
                                                    "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '>', start_date),
                                     ('date_start', '<', end_date)])]
            else:
                pro_selected = [int(data['project'])]
        elif start_date == 'null' and end_date != 'null':
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '<', end_date)])]
            else:
                pro_selected = [int(data['project'])]
        elif start_date != 'null' and end_date == 'null':
            start_date = datetime.datetime.strptime(start_date,
                                                    "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '>', start_date)])]
            else:
                pro_selected = [int(data['project'])]
        else:
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search([])]
            else:
                pro_selected = [int(data['project'])]
        report_project = request.env['timesheets.analysis.report'].search(
            [('project_id', 'in', pro_selected),
             ('employee_id', 'in', emp_selected)])
        analytic_project = request.env['account.analytic.line'].search(
            [('project_id', 'in', pro_selected),
             ('employee_id', 'in', emp_selected)])
        margin = round(sum(report_project.mapped('margin')), 2)
        sale_orders = []
        for rec in analytic_project:
            if rec.order_id.id and rec.order_id.id not in sale_orders:
                sale_orders.append(rec.order_id.id)
        total_time = sum(analytic_project.mapped('unit_amount'))
        return {
            'total_project': pro_selected,
            'total_emp': emp_selected,
            'total_task': [rec.id for rec in request.env['project.task'].search(
                [('project_id', 'in', pro_selected)])],
            'hours_recorded': total_time,
            'list_hours_recorded': [rec.id for rec in analytic_project],
            'total_margin': margin,
            'total_so': sale_orders
        }

    @http.route('/get/call/tiles/data', auth='public', type='json')
    def get_tiles_data(self):
        try:
            # Debug: Check total FSM tasks
            all_fsm_tasks = request.env['project.task'].search_count([('is_fsm', '=', True)])
            _logger.info(f"Total FSM tasks: {all_fsm_tasks}")

            # Debug: Check active FSM tasks with projects
            active_fsm_tasks = request.env['project.task'].search_count([
                ('is_fsm', '=', True),
                ('active', '=', True),
                ('project_id', '!=', False)
            ])
            _logger.info(f"Active FSM tasks with projects: {active_fsm_tasks}")

            user_employee = request.env.user.partner_id
            domain = [('is_fsm', '=', True)]

            if not user_employee.user_has_groups('project.group_project_manager'):
                domain.append(('user_id', '=', request.env.uid))

            all_projects = request.env['project.project'].search(domain)

            all_tasks = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids)])

            un_assigned_task = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids),
                ('user_ids', '=', False)])

            # total_closed_task = request.env['project.task'].search([
            #     ('project_id', 'in', all_projects.ids),
            #     ('state', 'in', ['1_done', '1_canceled'])])

            total_closed_task = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids),
                ('stage_id.name', '=', 'Done')])

            # Calculate counts for FSM projects and tasks
            active_projects = all_projects.filtered(lambda p: p.stage_id.name not in ['Done', 'Canceled'])

            running_projects = all_projects.filtered(lambda p: p.stage_id.name == 'In Progress')
            done_projects = all_projects.filtered(lambda p: p.stage_id.name == 'Done')
            running_tasks = all_tasks.filtered(lambda t: t.state == '01_in_progress')
            # done_tasks = all_tasks.filtered(lambda t: t.state == '1_done')

            done_tasks = all_tasks.filtered(lambda t: t.stage_id.name == 'Done')
            # old code commented

            # today = datetime.today()
            # expired_yesterday = all_tasks.filtered(lambda p: p.date_deadline == yesterday)
            # will_expire_tomorrow = all_tasks.filtered(lambda p: p.date_deadline == tomorrow)
            # expired_today = all_tasks.filtered(lambda p: p.date_deadline == today)

            today = datetime.today() + timedelta(hours=5, minutes=30)
            yesterday = today - timedelta(days=1)
            tomorrow = today + timedelta(days=1)

            # Set time to end of day (23:59:59) for each date
            today_end = today.replace(hour=23, minute=59, second=59)
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59)
            tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)

            # Set time to start of day (00:00:00) for each date
            today_start = today.replace(hour=0, minute=0, second=0)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0)
            tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0)

            # Filter tasks based on deadline ranges
            expired_yesterday = all_tasks.filtered(
                lambda t: t.date_deadline and
                          yesterday_start <= t.date_deadline <= yesterday_end
            )

            expired_today = all_tasks.filtered(
                lambda t: t.date_deadline and
                          today_start <= t.date_deadline <= today_end
            )

            will_expire_tomorrow = all_tasks.filtered(
                lambda t: t.date_deadline and
                          tomorrow_start <= t.date_deadline <= tomorrow_end
            )

            # Get a valid task ID - modified query
            sample_task = request.env['project.task'].search([
                ('is_fsm', '=', True),
                ('active', '=', True),
                ('project_id', '!=', False)  # Ensure task has a project
            ], limit=1)

            # Debug logging
            _logger.info(f"Found task: {sample_task.name if sample_task else 'None'}")
            sample_task_id = sample_task.id if sample_task else None

            result = {
                'total_projects': len(all_projects),
                'active_projects': len(active_projects),
                'running_projects': len(running_projects),
                'done_projects': len(done_projects),
                'running_tasks': len(running_tasks),
                'done_tasks': len(done_tasks),
                'total_tasks': len(all_tasks),
                'un_assigned_task': len(un_assigned_task),
                'total_closed_task': len(total_closed_task),
                'expired_yesterday': len(expired_yesterday),
                'will_expire_tomorrow': len(will_expire_tomorrow),
                'expired_today': len(expired_today),
                'flag': 1,
            }

            return result

        except Exception as e:
            _logger.error(f"Error in get_tiles_data: {e}")
            return {
                'error': str(e),
                'flag': 0
            }

    @http.route('/get/call/data', auth='public', type='json')
    def get_task_data(self):
        user_employee = request.env.user.partner_id
        if user_employee.user_has_groups('project.group_project_manager'):
            request._cr.execute('''select project_task.name as task_name,
            pro.name as project_name from project_task
            Inner join project_project as pro on project_task.project_id
            = pro.id ORDER BY project_name ASC''')
            data = request._cr.fetchall()
            project_name = []
            for rec in data:
                project_name.append(list(rec))
            return {
                'project': project_name
            }
        else:
            all_project = request.env['project.project'].search(
                [('user_id', '=', request.env.uid)]).ids

            # print(" get_task_data all_project",all_project)
            all_tasks = request.env['project.task'].search(
                [('project_id', 'in', all_project)])
            task_project = [[task.name, task.project_id.name] for task in
                            all_tasks]
            return {
                'project': task_project
            }

    @http.route('/call/task/by_tags', auth='public', type='json')
    def get_task_by_tags(self):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        # domain = request.env['project.project'].search([('is_fsm', '=', True)])
        if not user_employee.user_has_groups('industry_fsm.group_fsm_manager'):
            projects = request.env['project.project'].search([('user_id', '=', request.env.uid)])
            domain = [('project_id', 'in', projects.ids)]
        # Get all tasks with tags
        tasks = request.env['project.task'].search(domain)
        tag_count = {}
        # Count tasks for each tag
        for task in tasks:
            for tag in task.tag_ids:
                tag_count[tag.name] = tag_count.get(tag.name, 0) + 1

        # Prepare data for chart
        return {
            'labels': list(tag_count.keys()),
            'data': list(tag_count.values()),
            'colors': [
                          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                          '#FF9F40', '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0'
                      ][:len(tag_count)]
        }

    # this code only  Emplopyee Task Distribution
    @http.route('/call/task/by_employee', auth='public', type='json')
    def get_task_by_employee(self):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        if not user_employee.user_has_groups('project.group_project_manager'):
            projects = request.env['project.project'].search([('user_id', '=', request.env.uid)])
            domain = [('project_id', 'in', projects.ids)]

        # Get all tasks with assigned users
        tasks = request.env['project.task'].search(domain)
        employee_count = {}

        # Count tasks for each employee
        for task in tasks:
            for user in task.user_ids:
                employee_name = user.name
                employee_count[employee_name] = employee_count.get(employee_name, 0) + 1

        # Sort by task count in descending order and limit to top 10
        sorted_data = dict(sorted(employee_count.items(), key=lambda x: x[1], reverse=True)[:10])

        return {
            'labels': list(sorted_data.keys()),
            'data': list(sorted_data.values()),
            'colors': [
                '#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22',
                '#e74c3c', '#1abc9c', '#34495e', '#95a5a6', '#16a085'
            ]
        }

    # @http.route('/get/hours', auth='public', type='json')
    # def get_hours_data(self):
    #     user_employee = request.env.user.partner_id
    #     if user_employee.user_has_groups('project.group_project_manager'):
    #         query = '''SELECT sum(unit_amount) as hour_recorded FROM
    #            account_analytic_line WHERE
    #            timesheet_invoice_type='non_billable_project' '''
    #         request._cr.execute(query)
    #         data = request._cr.dictfetchall()
    #         hour_recorded = []
    #         for record in data:
    #             hour_recorded.append(record.get('hour_recorded'))
    #         query = '''SELECT sum(unit_amount) as hour_recorde FROM
    #            account_analytic_line WHERE
    #            timesheet_invoice_type='billable_time' '''
    #         request._cr.execute(query)
    #         data = request._cr.dictfetchall()
    #         hour_recorde = []
    #         for record in data:
    #             hour_recorde.append(record.get('hour_recorde'))
    #         query = '''SELECT sum(unit_amount) as billable_fix FROM
    #            account_analytic_line WHERE
    #            timesheet_invoice_type='billable_fixed' '''
    #         request._cr.execute(query)
    #         data = request._cr.dictfetchall()
    #         billable_fix = []
    #         for record in data:
    #             billable_fix.append(record.get('billable_fix'))
    #         query = '''SELECT sum(unit_amount) as non_billable FROM
    #            account_analytic_line WHERE timesheet_invoice_type='non_billable'
    #            '''
    #         request._cr.execute(query)
    #         data = request._cr.dictfetchall()
    #         non_billable = []
    #         for record in data:
    #             non_billable.append(record.get('non_billable'))
    #         query = '''SELECT sum(unit_amount) as total_hr FROM
    #            account_analytic_line WHERE
    #            timesheet_invoice_type='non_billable_project' or
    #            timesheet_invoice_type='billable_time' or
    #            timesheet_invoice_type='billable_fixed' or
    #            timesheet_invoice_type='non_billable' '''
    #         request._cr.execute(query)
    #         data = request._cr.dictfetchall()
    #         total_hr = []
    #         for record in data:
    #             total_hr.append(record.get('total_hr'))
    #         return {
    #             'hour_recorded': hour_recorded,
    #             'hour_recorde': hour_recorde,
    #             'billable_fix': billable_fix,
    #             'non_billable': non_billable,
    #             'total_hr': total_hr,
    #         }
    #     else:
    #         all_project = request.env['project.project'].search(
    #             [('user_id', '=', request.env.uid)]).ids
    #         analytic_project = request.env['account.analytic.line'].search(
    #             [('project_id', 'in', all_project)])
    #         all_hour_recorded = analytic_project.filtered(
    #             lambda x: x.timesheet_invoice_type == 'non_billable_project')
    #         all_hour_recorde = analytic_project.filtered(
    #             lambda x: x.timesheet_invoice_type == 'billable_time')
    #         all_billable_fix = analytic_project.filtered(
    #             lambda x: x.timesheet_invoice_type == 'billable_fixed')
    #         all_non_billable = analytic_project.filtered(
    #             lambda x: x.timesheet_invoice_type == 'non_billable')
    #         hour_recorded = [sum(all_hour_recorded.mapped('unit_amount'))]
    #         hour_recorde = [sum(all_hour_recorde.mapped('unit_amount'))]
    #         billable_fix = [sum(all_billable_fix.mapped('unit_amount'))]
    #         non_billable = [sum(all_non_billable.mapped('unit_amount'))]
    #         total_hr = [
    #             sum(hour_recorded + hour_recorde + billable_fix + non_billable)]
    #         return {
    #             'hour_recorded': hour_recorded,
    #             'hour_recorde': hour_recorde,
    #             'billable_fix': billable_fix,
    #             'non_billable': non_billable,
    #             'total_hr': total_hr,
    #         }

    # # new function addfed in this
    @http.route('/call/today', auth='public', type='json')
    def get_calls_today(self):

        employee_department = request.env['hr.department'].search([])
        for rec in employee_department:
            print(" dep", rec.name)
            print("employee_department", employee_department)

        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        if not user_employee.user_has_groups('project.group_project_manager'):
            domain.append(('user_id', '=', request.env.uid))

        all_projects = request.env['project.project'].search(domain)

        # Get today's date in the user's timezone
        user_tz = pytz.timezone(request.env.user.tz or 'UTC')
        today = datetime.now(user_tz).date()

        # Base domain for today's tasks
        today_domain = [
            ('project_id', 'in', all_projects.ids),
            ('create_date', '>=', datetime.combine(today, datetime.min.time())),
            ('create_date', '<=', datetime.combine(today, datetime.max.time()))
        ]

        # new task count show
        new_stage_domain = today_domain + [('stage_id.name', '=', 'New'), ('user_ids', '!=', False)]

        new_stage_tasks_today = request.env['project.task'].search(new_stage_domain)
        # new_stage_tasks_today = request.env['project.task'].search_count(new_stage_domain)

        # Get assigned tasks
        assigned_domain = today_domain + [('user_ids', '!=', False)]
        assigned_tasks = request.env['project.task'].search_count(assigned_domain)

        # Get unassigned tasks
        unassigned_domain = today_domain + [('user_ids', '=', False)]
        unassigned_tasks = request.env['project.task'].search_count(unassigned_domain)

        # Get closed tasks (assuming 'Done' stage indicates closed)
        closed_domain = today_domain + [('stage_id.name', '=', 'Done')]
        closed_tasks = request.env['project.task'].search_count(closed_domain)

        # Get on hold tasks (assuming there's a stage named 'On Hold')
        on_hold_domain = today_domain + [('stage_id.name', '=', 'On Hold')]
        on_hold_tasks = request.env['project.task'].search_count(on_hold_domain)

        result = {
            'new_stage_tasks_today': len(new_stage_tasks_today),
            'calls_assigned_today': assigned_tasks,
            'calls_unassigned_today': unassigned_tasks,
            'calls_closed_today': closed_tasks,
            'calls_on_hold_today': on_hold_tasks
        }
        return result

    @http.route('/previous/total', auth='public', type='json')
    def get_previous_total(self, **kw):
        try:
            user_employee = request.env.user.partner_id
            domain = [('is_fsm', '=', True)]

            start_date = kw.get('start_date')
            end_date = kw.get('end_date')

            if not user_employee.user_has_groups('project.group_project_manager'):
                domain.append(('user_id', '=', request.env.uid))

            all_projects = request.env['project.project'].search(domain)
            task_domain = [('project_id', 'in', all_projects.ids)]

            if start_date and end_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    task_domain += [
                        ('create_date', '>=', start_datetime),
                        ('create_date', '<', end_datetime)
                    ]
                except ValueError as e:
                    _logger.error(f"Date parsing error: {e}")

            all_tasks = request.env['project.task'].search(task_domain)

            assigned_count = len(all_tasks.filtered(lambda t: t.user_ids))
            unassigned_count = len(all_tasks.filtered(lambda t: not t.user_ids))
            on_hold_count = len(all_tasks.filtered(lambda t: t.stage_id.name == 'On Hold'))
            closed_count = len(all_tasks.filtered(lambda t: t.stage_id.name == 'Done'))

            return {
                'all_assigned_tasks_total': assigned_count,
                'all_unassigned_tasks_total': unassigned_count,
                'all_on_hold_tasks_total': on_hold_count,
                'all_closed_tasks_total': closed_count,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_previous_total: {e}")
            return {
                'all_assigned_tasks_total': 0,
                'all_unassigned_tasks_total': 0,
                'all_on_hold_tasks_total': 0,
                'all_closed_tasks_total': 0,
                'date_range': {'start': None, 'end': None}
            }

    @http.route('/get/task/details', auth='public', type='json')
    def get_task_details(self, task_id):
        try:
            if not task_id:
                return {'error': 'No task ID provided'}

            task = request.env['project.task'].browse(int(task_id))
            print("task ",task)
            if not task.exists():
                return {'error': 'Task not found'}

            return {
                'id': task.id,
                'name': task.name,
                'exists': True,
                'project': task.project_id.name if task.project_id else None
            }
        except Exception as e:
            _logger.error(f"Error fetching task details: {e}")
            return {'error': str(e)}

    @http.route('/get/fsm/project', auth='public', type='json')
    def get_fsm_project(self):
        try:
            # Get the Field Service project
            fsm_project = request.env['project.project'].search([
                ('is_fsm', '=', True),
                ('name', '=', 'Field Service')  # or whatever your FSM project name is
            ], limit=1)

            if not fsm_project:
                # If no FSM project found, create one
                fsm_project = request.env['project.project'].create({
                    'name': 'Field Service',
                    'is_fsm': True,
                })

            # Get current user
            current_user = request.env.user

            return {
                'id': fsm_project.id,
                'name': fsm_project.name,
                'user_id': current_user.id,
                'user_name': current_user.name
            }
        except Exception as e:
            _logger.error(f"Error getting FSM project: {e}")
            return False





