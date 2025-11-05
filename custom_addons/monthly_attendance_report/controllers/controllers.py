import io
import xlsxwriter
from calendar import monthrange
from odoo import http
from odoo.http import request, Response
from werkzeug.http import dump_options_header
import json
from odoo.fields import Date


class MonthlyAttendanceReportController(http.Controller):

    @http.route('/web/monthly_attendance_report/export_xlsx', type='http', auth='user')
    def export_attendance_report(self, **kwargs):
        month = kwargs.get('month')
        department_names = kwargs.get('department_names', '').split(',') if kwargs.get('department_names') else []
        employee_names = kwargs.get('employee_names', '').split(',') if kwargs.get('employee_names') else []
        department_ids = kwargs.get('department_ids', '').split(',') if kwargs.get('department_ids') else []
        employee_ids = kwargs.get('employee_ids', '').split(',') if kwargs.get('employee_ids') else []

        # Build domain to match exactly what frontend shows
        domain = []

        if month:
            try:
                year, month_num = map(int, month.split('-'))
                start_date = f"{year}-{month_num:02d}-01"
                last_day = monthrange(year, month_num)[1]
                end_date = f"{year}-{month_num:02d}-{last_day}"
                domain += [('report_date', '>=', start_date), ('report_date', '<=', end_date)]
            except Exception as e:
                return request.make_response(f"Invalid month format: {month}", status=400)
        else:
            return request.make_response("Month is required", status=400)

        # Apply filters exactly like the original logic but without regeneration
        if department_ids:
            try:
                dept_ids = [int(dept_id) for dept_id in department_ids if dept_id]
                if dept_ids:
                    domain.append(('department_id', 'in', dept_ids))
            except (ValueError, TypeError):
                if department_names:
                    domain.append(('department_id.name', 'in', department_names))
        elif department_names:
            domain.append(('department_id.name', 'in', department_names))

        if employee_ids:
            try:
                emp_ids = [int(emp_id) for emp_id in employee_ids if emp_id]
                if emp_ids:
                    domain.append(('employee_id', 'in', emp_ids))
            except (ValueError, TypeError):
                if employee_names:
                    domain.append(('employee_id.name', 'in', employee_names))
        elif employee_names:
            domain.append(('employee_id.name', 'in', employee_names))

        # Only get existing report lines that match the frontend filters
        # DO NOT regenerate - only export what's already visible in frontend
        report_lines = request.env['monthly.attendance.report.line'].sudo().search_read(
            domain,
            fields=[
                'employee_code','employee_id', 'department_id', 'company_id',
                'total_days', 'working_days', 'weekoff','present_days', 'deduction_days',
                'late_in', 'early_out', 'extra_days',
                'paid_leaves', 'unpaid_leaves', 'uninformed_leave','public_holidays', 'pay_days', 'daily_attendance_data'
            ]
        )

        # If no records found with current filters, return error
        if not report_lines:
            return request.make_response("No records found with current filters. Please view the report first.", status=404)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Attendance Report')

        # Format definitions
        center_wrap_format = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'})
        date_header_format = header_format
        in_out_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter'})
        red_header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#FF0000'})
        orange_header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#FFA500'})
        red_cell_format = workbook.add_format({'bg_color': '#FF0000', 'align': 'center', 'valign': 'vcenter'})
        orange_cell_format = workbook.add_format({'bg_color': '#FFA500', 'align': 'center', 'valign': 'vcenter'})
        public_holiday_format = workbook.add_format({'bg_color': '#D3D3D3', 'align': 'center', 'valign': 'vcenter'})

        column_widths = {}

        def track_column_width(col_idx, value):
            if isinstance(value, (int, float)):
                length = len(str(value))
            elif isinstance(value, str):
                length = len(value)
            else:
                length = 0
            column_widths[col_idx] = max(column_widths.get(col_idx, 0), length)

        if month:
            year, month_num = map(int, month.split('-'))
            total_days = monthrange(year, month_num)[1]
        else:
            total_days = 31

        header_row = 0
        static_headers = [
            'Employee Code','Employee', 'Department', 'Company',
            'Total Days', 'Working Days', 'WeekOff','Present Days', 'Deduction Days',
            'Late In', 'Early Out', 'Extra Days',
            'Paid Leaves', 'Unpaid Leaves', 'Uninformed Leave', 'Public Holidays', 'Pay Days'
        ]

        current_col = 0
        for header in static_headers:
            if header in ['Late In', 'Early Out']:
                fmt = red_header_format
            elif header in ['Paid Leaves', 'Unpaid Leaves']:
                fmt = orange_header_format
            else:
                fmt = header_format
            sheet.write(header_row, current_col, header, fmt)
            track_column_width(current_col, header)
            current_col += 1

        entry_type_col = len(static_headers)
        sheet.write(header_row, entry_type_col, 'Entry Type', header_format)
        track_column_width(entry_type_col, 'Entry Type')

        date_start_col = entry_type_col + 1
        current_col = date_start_col

        for day_num in range(1, total_days + 1):
            sheet.write(header_row, current_col, str(day_num), date_header_format)
            track_column_width(current_col, str(day_num))
            current_col += 1

        current_data_row = 1

        for line in report_lines:
            # Get fresh record for daily attendance data
            fresh_record = request.env['monthly.attendance.report.line'].sudo().browse(line['id'])
            line['daily_attendance_data'] = fresh_record.daily_attendance_data

            employee_row_start = current_data_row
            employee_row_end = current_data_row + 1

            sheet.write(employee_row_start, entry_type_col, 'In', in_out_format)
            track_column_width(entry_type_col, 'In')
            sheet.write(employee_row_end, entry_type_col, 'Out', in_out_format)
            track_column_width(entry_type_col, 'Out')

            static_col = 0
            for header in static_headers:
                field_name = header.lower().replace(' ', '_')
                if field_name in ['employee', 'department', 'company']:
                    actual_field_name = f"{field_name}_id"
                else:
                    actual_field_name = field_name
                value = line.get(actual_field_name)
                if actual_field_name.endswith('_id'):
                    value = value[1] if value else ''
                elif value is False or value is None:
                    value = ''
                sheet.merge_range(employee_row_start, static_col, employee_row_end, static_col, value, center_wrap_format)
                track_column_width(static_col, value)
                static_col += 1

            daily_data = json.loads(line['daily_attendance_data'] or '{}')

            for day_index in range(total_days):
                day_num = day_index + 1
                daily_col = date_start_col + day_index
                day_data = daily_data.get(str(day_num), {})
                day_status = day_data.get('status', 'present')
                day_entries = day_data.get('entries', [])
                is_late_in = day_data.get('is_late_in', False)
                is_early_out = day_data.get('is_early_out', False)

                in_time = ''
                out_time = ''
                for entry in day_entries:
                    if entry.get('type') == 'in':
                        in_time = entry.get('time', '')
                    elif entry.get('type') == 'out':
                        out_time = entry.get('time', '')

                # Determine cell formatting based on day status and flags
                in_cell_format = center_wrap_format
                out_cell_format = center_wrap_format

                # Priority order: Public Holiday > Leave > Late/Early > Default
                if day_status == 'public_holiday':
                    in_cell_format = public_holiday_format
                    out_cell_format = public_holiday_format
                    in_time = 'H' if not in_time else in_time
                    out_time = 'H' if not out_time else out_time
                elif day_data.get('is_on_leave'):  # Prioritize any type of leave
                    in_cell_format = orange_cell_format
                    out_cell_format = orange_cell_format
                    in_time = 'L' if not in_time else in_time
                    out_time = 'L' if not out_time else out_time
                elif is_late_in:
                    in_cell_format = red_cell_format
                if is_early_out:
                    out_cell_format = red_cell_format

                sheet.write(employee_row_start, daily_col, in_time, in_cell_format)
                sheet.write(employee_row_end, daily_col, out_time, out_cell_format)

                track_column_width(daily_col, in_time)
                track_column_width(daily_col, out_time)

            current_data_row += 2

        for col_idx, width in column_widths.items():
            sheet.set_column(col_idx, col_idx, width + 2)

        workbook.close()
        output.seek(0)

        filename = f"Monthly_Attendance_Report_{month or 'All'}.xlsx"
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', dump_options_header('attachment', {'filename': filename}))
        ]
        return Response(output.read(), headers=headers)