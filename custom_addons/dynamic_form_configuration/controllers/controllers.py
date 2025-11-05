from odoo import http, _
from odoo.http import request
from lxml import etree


class MobileFieldsController(http.Controller):

    @http.route('/web/mobile_fields', type='json', auth='user')
    def get_mobile_fields(self):
        """
        API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
        Combines the fields from the model and the view, and filters based on 'for_mobile'.
        Includes visibility conditions extracted from the view XML using domain, groups, and invisible.
        """
        try:
            request_data = request.httprequest.get_json()
            model_name = request_data.get('model')
            view_xml_id = request_data.get('view_xml_id')

            if not model_name or not view_xml_id:
                return {'status': 'false', 'error': 'Model and view_xml_id are required'}

            if model_name not in request.env:
                return {'status': 'false', 'error': f'Model "{model_name}" does not exist.'}

            # Get model fields
            model_obj = request.env[model_name]
            fields_data = model_obj.fields_get()

            # Get view reference
            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': 'false', 'error': f'View {view_xml_id} not found'}

            # Get view architecture
            view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': 'false', 'error': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)

            # Combine fields from model and view (get intersection)
            model_fields = set(fields_data.keys())
            view_fields = set(field.get('name') for field in arch_tree.xpath("//field") if field.get('name'))
            common_fields = model_fields.intersection(view_fields)  # Get only common fields

            # Fetch 'for_mobile' fields
            mobile_field_model = request.env['ir.model.fields.mobile']
            mobile_fields = {}
            for_mobile_records = mobile_field_model.search(
                [('field_id.model', '=', model_name), ('for_mobile', '=', True)])

            # Collect fields marked as 'for_mobile' and present in both model and view
            for_mobile_fields = {rec.field_id.name for rec in for_mobile_records}

            # Process fields for response
            for field_name in common_fields:
                if field_name in for_mobile_fields:
                    field_info = fields_data.get(field_name, {})
                    # Find visibility conditions from the view using domain, groups, and invisible
                    view_field = arch_tree.xpath(f"//field[@name='{field_name}']")
                    visibility_conditions = None
                    invisible_condition = None

                    if view_field:
                        domain = view_field[0].get('domain', None)
                        groups = view_field[0].get('groups', None)
                        invisible_condition = view_field[0].get('invisible', None)

                        visibility_conditions = {
                            'domain': domain,
                            'groups': groups,
                            'invisible': invisible_condition
                        }

                    # Add field info with visibility conditions
                    mobile_fields[field_name] = {
                        'type': field_info.get('type'),
                        'string': field_info.get('string'),
                        'readonly': field_info.get('readonly'),
                        'required': field_info.get('required', False),
                        'selection': field_info.get('selection', []),
                        'depends': field_info.get('depends', False),
                        'visibility_conditions': visibility_conditions
                    }

            return {
                'status': 'success',
                'fields': mobile_fields
            }

        except Exception as e:
            return {'status': 'false', 'error': str(e)}


# from odoo import http
# from odoo.http import request
# from lxml import etree
#
#
# class MobileFieldsController(http.Controller):
#
#     @http.route('/web/mobile_fields', type='json', auth='user')
#     def get_mobile_fields(self):
#         """
#         API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
#         Only returns fields that are within form/sheet/field structure.
#         Includes visibility conditions extracted from the view XML.
#         """
#         try:
#             request_data = request.httprequest.get_json()
#             model_name = request_data.get('model')
#             view_xml_id = request_data.get('view_xml_id')
#
#             if not model_name or not view_xml_id:
#                 return {'status': 'false', 'error': 'Model and view_xml_id are required'}
#
#             if model_name not in request.env:
#                 return {'status': 'false', 'error': f'Model "{model_name}" does not exist.'}
#
#             # Get model fields
#             model_obj = request.env[model_name]
#             fields_data = model_obj.fields_get()
#
#             # Get view reference
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': 'false', 'error': f'View {view_xml_id} not found'}
#
#             # Get view architecture
#             view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': 'false', 'error': 'View architecture not found'}
#
#             arch_tree = etree.fromstring(arch)
#
#             # Get fields specifically within form/sheet structure
#             sheet_fields = arch_tree.xpath("//form//sheet//field")
#             sheet_field_names = set(field.get('name') for field in sheet_fields if field.get('name'))
#
#             # Fetch 'for_mobile' fields
#             mobile_field_model = request.env['ir.model.fields.mobile']
#             for_mobile_records = mobile_field_model.search([
#                 ('field_id.model', '=', model_name),
#                 ('for_mobile', '=', True)
#             ])
#
#             # Get fields marked as 'for_mobile'
#             for_mobile_fields = {rec.field_id.name for rec in for_mobile_records}
#
#             # Get intersection of sheet fields and for_mobile fields
#             valid_fields = sheet_field_names.intersection(for_mobile_fields)
#
#             # Process fields for response
#             mobile_fields = {}
#             for field_name in valid_fields:
#                 field_info = fields_data.get(field_name, {})
#
#                 # Find visibility conditions from the view
#                 view_field = arch_tree.xpath(f"//form//sheet//field[@name='{field_name}']")
#                 visibility_conditions = None
#
#                 if view_field:
#                     domain = view_field[0].get('domain', None)
#                     groups = view_field[0].get('groups', None)
#                     invisible_condition = view_field[0].get('invisible', None)
#
#                     visibility_conditions = {
#                         'domain': domain,
#                         'groups': groups,
#                         'invisible': invisible_condition
#                     }
#
#                 # Add field info with visibility conditions
#                 mobile_fields[field_name] = {
#                     'type': field_info.get('type'),
#                     'string': field_info.get('string'),
#                     'readonly': field_info.get('readonly'),
#                     'required': view_field[0].get('required', False),
#                     'selection': field_info.get('selection', []),
#                     'depends': field_info.get('depends', False),
#                     'visibility_conditions': visibility_conditions
#                 }
#
#             return {
#                 'status': 'success',
#                 'fields': mobile_fields
#             }
#
#         except Exception as e:
#             return {'status': 'false', 'error': str(e)}


import pytz
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class AttendanceController(http.Controller):

    @http.route('/web/attendance_dashboard', type='json', auth='user')
    def get_attendance_data(self, user_id, date):
        try:
            selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            today_date = datetime.now().date()

            # Show only leave data for future dates
            if selected_date > today_date:
                leave_info = []
                employees = request.env['hr.employee'].search([('parent_id.user_id', '=', user_id)])
                if not employees:
                    return {'message': 'No employees found under this user'}

                for employee in employees:
                    leave = request.env['hr.leave'].search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'validate'),
                        ('request_date_from', '<=', selected_date),
                        ('request_date_to', '>=', selected_date)
                    ])

                    profile_picture = employee.image_1920

                    if leave:
                        for l in leave:
                            leave_info.append({
                                'leave_type': l.holiday_status_id.name,
                                'leave_status': l.state,
                                'employee': employee.name,
                                'date': selected_date.strftime('%Y-%m-%d'),
                                'work_phone': employee.work_phone,
                                'work_mobile': employee.mobile_phone,
                                'picture': profile_picture,
                            })
                return {'present': [],
                        'absent': [],
                        'late_checkin': [],
                        'early_checkout': [], 'leave': leave_info, 'all_data': leave_info}
            user = request.env['res.users'].browse(user_id)

            if not user.exists():
                return {'error': 'Invalid user ID'}

            user_timezone = pytz.timezone(user.tz or 'UTC')

            start_of_day = user_timezone.localize(
                datetime.combine(selected_date, datetime.min.time())
            ).astimezone(pytz.utc)
            end_of_day = user_timezone.localize(
                datetime.combine(selected_date, datetime.max.time())
            ).astimezone(pytz.utc)

            late_allowance_minutes = int(
                request.env['ir.config_parameter'].sudo().get_param('attendance.minute_allowed', default=0)
            )

            employees = request.env['hr.employee'].search([('parent_id.user_id', '=', user_id)])
            if not employees:
                return {'message': 'No employees found under this user'}

            results = {
                'present': [],
                'absent': [],
                'leave': [],
                'late_checkin': [],
                'early_checkout': [],
                'all_data': [],
            }

            for employee in employees:

                attendances = request.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', start_of_day),
                    ('check_in', '<=', end_of_day)
                ])

                leave = request.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '<=', selected_date),
                    ('request_date_to', '>=', selected_date)
                ])

                resource_calendar = employee.resource_calendar_id
                work_from_hour = 9
                work_to_hour = 18

                if resource_calendar:
                    weekday = selected_date.weekday()
                    for calendar_attendance in resource_calendar.attendance_ids:
                        if int(calendar_attendance.dayofweek) == weekday and calendar_attendance.day_period == 'morning':
                            work_from_hour = int(calendar_attendance.hour_from)

                        if int(calendar_attendance.dayofweek) == weekday and calendar_attendance.day_period == 'evening':
                            work_to_hour = int(calendar_attendance.hour_to)

                profile_picture = employee.image_1920

                if attendances:
                    first_attendance = attendances[-1]
                    check_in_time_utc = first_attendance.check_in
                    check_in_time_local = check_in_time_utc.astimezone(user_timezone).time()

                    total_minutes = int(work_from_hour * 60) + late_allowance_minutes
                    allowed_time = timedelta(minutes=total_minutes)

                    if check_in_time_local > (datetime.min + allowed_time).time():
                        results['late_checkin'].append({
                            'employee': employee.name,
                            'check_in': first_attendance.check_in.astimezone(user_timezone),
                            'check_in_latitude': first_attendance.in_latitude,
                            'check_in_longitude': first_attendance.in_longitude,
                            'check_in_Address': first_attendance.check_in_address,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'picture': profile_picture,

                        })

                    last_attendance = attendances[0]
                    check_out_time_utc = last_attendance.check_out
                    check_out_time_local = check_out_time_utc.astimezone(
                        user_timezone).time() if check_out_time_utc else None

                    expected_end_time = timedelta(hours=work_to_hour)

                    if check_out_time_local and datetime.min + timedelta(hours=check_out_time_local.hour,
                                                                         minutes=check_out_time_local.minute) < datetime.min + expected_end_time:
                        results['early_checkout'].append({
                            'employee': employee.name,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in': last_attendance.check_in.astimezone(user_timezone),
                            'check_in_latitude': last_attendance.in_latitude,
                            'check_in_longitude': last_attendance.in_longitude,
                            'check_in_Address': last_attendance.check_in_address,
                            'check_out': last_attendance.check_out and last_attendance.check_out.astimezone(
                                user_timezone),
                            'check_out_Address': last_attendance.check_out_address,
                            'check_out_latitude': last_attendance.out_latitude,
                            'check_out_longitude': last_attendance.out_longitude,
                            'picture': profile_picture,
                        })

                    for attendance in attendances:
                        results['present'].append({
                            'employee': employee.name,
                            'check_in': attendance.check_in.astimezone(user_timezone),
                            'check_out': attendance.check_out and attendance.check_out.astimezone(user_timezone),
                            'check_in_Address': attendance.check_in_address,
                            'check_out_Address': attendance.check_out_address,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in_latitude': attendance.in_latitude,
                            'check_in_longitude': attendance.in_longitude,
                            'check_out_latitude': attendance.out_latitude,
                            'check_out_longitude': attendance.out_longitude,
                            'picture': profile_picture,
                        })
                        results['all_data'].append({
                            'employee': employee.name,
                            'check_in': attendance.check_in.astimezone(user_timezone),
                            'check_out': attendance.check_out and attendance.check_out.astimezone(user_timezone),
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in_latitude': attendance.in_latitude,
                            'check_in_longitude': attendance.in_longitude,
                            'check_out_latitude': attendance.out_latitude,
                            'check_out_longitude': attendance.out_longitude,
                            'check_in_Address': attendance.check_in_address,
                            'check_out_Address': attendance.check_out_address,
                            'picture': profile_picture,

                        })

                elif leave:
                    leave_info = []
                    for l in leave:
                        leave_info.append({
                            'leave_type': l.holiday_status_id.name,
                            'leave_status': l.state,
                            'employee': employee.name,
                            'date': selected_date.strftime('%Y-%m-%d'),

                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'picture': profile_picture,
                        })
                    results['leave'].extend(leave_info)
                    results['all_data'].append({'employee': employee.name,
                                                'work_phone': employee.work_phone,
                                                'work_mobile': employee.mobile_phone, 'status': 'On Leave',
                                                'date': selected_date.strftime('%Y-%m-%d'),
                                                'picture': profile_picture,
                                                })

                else:
                    results['absent'].append({'employee': employee.name, 'work_phone': employee.work_phone,
                                              'work_mobile': employee.mobile_phone,
                                              'date': selected_date.strftime('%Y-%m-%d'), 'picture': profile_picture,

                                              })
                    results['all_data'].append({'employee': employee.name, 'work_phone': employee.work_phone,
                                                'work_mobile': employee.mobile_phone, 'status': 'Absent',
                                                'date': selected_date.strftime('%Y-%m-%d'), 'picture': profile_picture,
                                                })

            return results

        except Exception as e:
            return {'error': str(e)}


# {
#     "jsonrpc": "2.0",
#     "id": 97,
#     "method": "call",
#     "params": {
#               "user_id": 2,
#                 "date": "2025-02-05"
#         }
# }


