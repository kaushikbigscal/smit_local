from pytz import timezone
from datetime import datetime
from odoo import http
from odoo.http import request
from pytz import timezone, UTC


class ChatterDownloadController(http.Controller):

    @http.route('/get/fetch_ticket_number', type='json', auth='user')
    def fetch_ticket_number(self, task_id):
        task = request.env['project.task'].sudo().browse(task_id)

        user_tz = request.env.user.tz or 'UTC'
        tz = timezone(user_tz)
        if not task or not task.is_fsm:
            return {'ticket_number': 'Undefined'}

        task.is_fsm = True

        # Fetch start and end dates from DateRange field
        start_date = task.planned_date_begin.astimezone(tz).strftime(
            '%m-%d-%Y %H:%M:%S') if task.planned_date_begin else 'N/A'
        end_date = task.date_deadline.astimezone(tz).strftime('%m-%d-%Y %H:%M:%S') if task.date_deadline else 'N/A'
        priority_label = dict(task._fields['priority'].selection).get(task.priority, 'N/A')
        if task.priority == '1':
            priority_label = 'High'
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', task.id)
        ])
        base_url = request.httprequest.host_url.rstrip('/')
        non_image_attachments = []

        for attach in attachments:
            print(f"Attachment ID: {attach.id}")
            if not attach.mimetype.startswith('image/'):
                local_dt = attach.create_date.replace(tzinfo=UTC).astimezone(tz)
                formatted_dt = local_dt.strftime('%d/%m/%Y, %I:%M:%S %p')
                non_image_attachments.append({
                    'id': attach.id,
                    'name': attach.name,
                    'url': f'{base_url}/web/content/{attach.id}',
                    'mimetype': attach.mimetype,
                    'create_date': formatted_dt,
                })

        assignees = []

        # sub_call_assignees = []
        if task.call_sub_types == 'join_call':
            sub_calls = request.env['project.task'].sudo().search([
                ('parent_id', '=', task.id),
                ('is_fsm', '=', True),
            ])
            # Collect all assignee names from sub-calls
            for sub_call in sub_calls:
                sub_assignees = sub_call.user_ids.mapped('name')
                assignees.extend(sub_assignees)

            # Remove duplicates
            assignees = list(set(assignees))

        return {
            'ticket_number': task.sequence_fsm or 'Undefined',
            'assignee': [user.name for user in task.user_ids] or [],
            # 'call_type': task.call_type or 'N/A',
            'call_type': (task.call_type.name if task.call_type else 'N/A'),
            'complaint_type': ', '.join(task.complaint_type_id.mapped('name')) if task.complaint_type_id else 'N/A',
            'reason_code_id': ', '.join(task.reason_code_id.mapped('name')) if task.reason_code_id else 'N/A',
            'call_name': task.name or 'N/A',
            'customer': task.partner_id.name if task.partner_id else 'N/A',
            'customer_product_id': task.customer_product_id.product_id.name if task.customer_product_id.product_id else '',
            'serial_number': ', '.join(task.serial_number.mapped('name')) if task.serial_number else '',
            'service_types': task.service_types.name if task.service_types else '',
            'call_coordinator_id': task.call_coordinator_id.name if task.call_coordinator_id else '',
            'call_coordinator_phone': task.call_coordinator_id.phone if task.call_coordinator_id and task.call_coordinator_id.phone else '',
            'problem_description': task.problem_description or 'N/A',
            'fix_description': task.fix_description or 'N/A',
            'stage_name': task.stage_id.name if task.stage_id else 'No Stage',
            'start_date': start_date,
            'end_date': end_date,
            'priority': priority_label,
            'call_sub_types': dict(task._fields['call_sub_types'].selection).get(task.call_sub_types, 'N/A') or '',
            'call_sub_type_assignee': assignees or 'N/A',
            'task_id': task.id,
            'is_fsm': task.is_fsm,
            'attachments': non_image_attachments,

        }
