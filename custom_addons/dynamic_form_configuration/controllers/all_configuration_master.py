from odoo import http
from odoo.http import request
from odoo.tools import json


class ConfigurationMaster(http.Controller):
    @http.route('/web/get/company_user_flag', auth='user')
    def get_service_call_flags(self):
        user = request.env.user
        company = request.env.company

        config = request.env['ir.config_parameter'].sudo()
        settings = request.env['res.config.settings'].sudo().get_values()

        leave_type_id = settings.get('leave_type_id')
        leave_type = request.env['hr.leave.type'].sudo().browse(leave_type_id) if leave_type_id else False
        leave_type_name = leave_type.name if leave_type and leave_type.exists() else ''

        company_flags = {
            'Service Call Geofencing': {
                'enable_geofence_service': bool(company.enable_geofence_service),
                'allowed_distance_service': float(company.allowed_distance_service),
                'enable_geofencing_on_checkin': bool(company.enable_geofencing_on_checkin),
                'enable_geofencing_on_checkout': bool(company.enable_geofencing_on_checkout),
            },
            'Attendance Geofencing': {
                'enable_geofence': bool(company.enable_geofence),
                'enable_geofence_day_out': bool(company.enable_geofence_day_out),
                'company_latitude': float(company.company_latitude),
                'company_longitude': float(company.company_longitude),
                'allowed_distance': float(company.allowed_distance),
            },
            'Service Call': {
                'resolved_required_fields': [field.name for field in company.resolved_required_fields],
                'attachment_required': bool(company.attachment_required),
                'signed_required': bool(company.signed_required),
            },
            'Remainder Settings': {
                'day_in_reminder_enabled': bool(company.day_in_reminder_enabled),
                'day_out_reminder_enabled': bool(company.day_out_reminder_enabled),
                'auto_day_out': bool(company.auto_day_out),
            }
        }

        user_flags = {
            'Service Call Geofencing': {
                'enable_geofence_service': bool(user.enable_geofence_service),
                'enable_geofencing_on_checkin': bool(user.enable_geofencing_on_checkin),
                'enable_geofencing_on_checkout': bool(user.enable_geofencing_on_checkout),
            },
            'Attendance Geofencing': {
                'enable_geofence': bool(user.enable_geofence),
                'enable_geofence_day_out': bool(user.enable_geofence_day_out),
            },
            'Remainder Settings': {
                'day_in_reminder_enabled': bool(user.day_in_reminder_enabled),
                'day_out_reminder_enabled': bool(user.day_out_reminder_enabled),
                'auto_day_out': bool(user.auto_day_out),
            }
        }

        settings_level_flag = {
            'Service Call': {
                'service_planned_stage': bool(config.get_param('industry_fsm.service_planned_stage')),
                'service_resolved_stage': bool(config.get_param('industry_fsm.service_resolved_stage')),
                'service_call_dependencies': bool(config.get_param('industry_fsm.service_call_dependencies'))
            },
            'System Reminder': {
                'reminder_day_in_offset_minutes': int(config.get_param('reminder.day_in_offset_minutes')),
                'reminder_day_out_offset_minutes': int(config.get_param('reminder.day_out_offset_minutes')),
                'enable_overdue_reminder': settings.get('enable_overdue_reminder'),
                'overdue_reminder_times': config.get_param('overdue_task_reminder.times', default=''),
            },
            'Attendance': {
                'max_late_check_ins': settings.get('max_late_check_ins'),
                'max_early_check_outs': settings.get('max_early_check_outs'),
                'minute_allowed': settings.get('minute_allowed'),
                'notification_late_day_in': settings.get('notification_late_day_in'),
                'leave_type': {
                    'name': leave_type_name,
                }
            }
        }

        return request.make_response(
            json.dumps({
                'Company Level': company_flags,
                'User Level': user_flags,
                'Settings Level': settings_level_flag,
            }),
            headers=[('Content-Type', 'application/json')]
        )
