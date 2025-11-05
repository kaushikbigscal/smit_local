from odoo import http
from odoo.http import request
import io
import xlsxwriter
import logging
from collections import defaultdict
from datetime import datetime
_logger = logging.getLogger(__name__)

class ExcelReportController(http.Controller):

    @http.route('/download/excel_report', type='http', auth='user')
    def download_excel_report(self, **kwargs):
        try:
            month = kwargs.get('month')
            if not month:
                return request.make_response('Month not specified.', status=400)
            # Parse month
            selected_month = datetime.strptime(month, '%m/%Y')
            start_date = selected_month.replace(day=1)
            if selected_month.month == 12:
                end_date = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
            else:
                end_date = selected_month.replace(month=selected_month.month + 1, day=1)

            # Fetch tasks in selected month
            tasks = request.env['project.task'].sudo().search([
                ('is_fsm', '=', True),
                ('project_id', '!=', False),
                ('active','=',True),
                ('display_in_project', '=', True),
                ('create_date', '>=', start_date),
                ('create_date', '<', end_date),
            ])
            _logger.info(f"Found {len(tasks)},{tasks} tasks in the selected month.")

            data_by_date = defaultdict(lambda: {
                'field_engineer': {'present': 0, 'absent': 0},
                'total': {'registered': 0, 'allocated': 0, 'completed': 0, 'pending': 0},
                'chargeable': {'registered': 0, 'allocated': 0, 'completed': 0, 'value': 0.0},
                'amc': {'registered': 0, 'completed': 0, 'pending': 0},
                'warranty': {'registered': 0, 'installation': 0, 'completed': 0, 'pending': 0},
                'free': {'registered': 0, 'completed': 0, 'pending': 0},
            })

            all_dates = set()
            for task in tasks:
                if task.create_date:
                    all_dates.add(task.create_date.date())

            service_division = request.env['hr.department'].sudo().search([('name', '=', 'Service Division')], limit=1)
            employees = []
            if service_division:
                employees = request.env['hr.employee'].sudo().search([
                    ('department_id.parent_id', '=', service_division.id)
                ])
                total_field_engineers = len(employees)

            attendance_model = request.env['hr.attendance'].sudo()
            attendance_records = attendance_model.search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', start_date),
                ('check_in', '<', end_date),
            ])

            attendance_map = defaultdict(set) 
            for att in attendance_records:
                att_date = att.check_in.date()
                attendance_map[att.employee_id.id].add(att_date)

            for task in tasks:
                if not task.create_date:
                    continue

                date_only = task.create_date.date()
                stage = task.stage_id.name.lower() if task.stage_id else ''
                call_type_name = ''
                if task.call_type:
                    call_type_name = task.call_type.name.lower() if hasattr(task.call_type, 'name') else str(
                        task.call_type).lower()
                is_done_or_resolved = stage in ['done', 'resolved']

                # Total
                data_by_date[date_only]['total']['registered'] += 1
                if task.user_ids:
                    data_by_date[date_only]['total']['allocated'] += 1
                if is_done_or_resolved:
                    data_by_date[date_only]['total']['completed'] += 1
                else:
                    data_by_date[date_only]['total']['pending'] += 1

                # Chargeable
                if call_type_name == 'chargeable':
                    data_by_date[date_only]['chargeable']['registered'] += 1
                    if task.user_ids:
                        data_by_date[date_only]['chargeable']['allocated'] += 1
                    if is_done_or_resolved:
                        data_by_date[date_only]['chargeable']['completed'] += 1
                    charge = task.total_charge or 0.0
                    data_by_date[date_only]['chargeable']['value'] += charge

                # AMC
                elif call_type_name == 'amc':
                    data_by_date[date_only]['amc']['registered'] += 1
                    if is_done_or_resolved:
                        data_by_date[date_only]['amc']['completed'] += 1
                    else:
                        data_by_date[date_only]['amc']['pending'] += 1

                # Warranty
                elif call_type_name == 'warranty':
                    data_by_date[date_only]['warranty']['registered'] += 1
                    if 'installation' in (task.name or '').lower():
                        data_by_date[date_only]['warranty']['installation'] += 1
                    if is_done_or_resolved:
                        data_by_date[date_only]['warranty']['completed'] += 1
                    else:
                        data_by_date[date_only]['warranty']['pending'] += 1

                # Free
                elif call_type_name == 'free':
                    data_by_date[date_only]['free']['registered'] += 1
                    if is_done_or_resolved:
                        data_by_date[date_only]['free']['completed'] += 1
                    else:
                        data_by_date[date_only]['free']['pending'] += 1

                all_report_dates = set(data_by_date.keys()) | all_dates
                for date in all_report_dates:
                    present_count = 0
                    absent_count = 0
                    for emp in employees:
                        if date in attendance_map[emp.id]:
                            present_count += 1
                        else:
                            absent_count += 1
                    # Store counts
                    data_by_date[date]['field_engineer']['present'] = present_count
                    data_by_date[date]['field_engineer']['absent'] = absent_count

            # Excel generation
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet("Call Type Wise Summary Report.")

            # === Formats ===
            title_format = workbook.add_format({'bold':True,'align':'left','font_size':14, 'valign': 'vcenter'})

            header_format = workbook.add_format({
                'bold': True, 'align': 'center', 'valign': 'center',
                'bg_color': '#4F81BD', 'font_color': 'white', 'border': 1
            })
            subheader_format = workbook.add_format({
                'bold': True, 'align': 'center', 'valign': 'center',
                'bg_color': '#D9E1F2', 'border': 1
            })

            empty_format = workbook.add_format({'bold':True,'align':'center', 'font_size': 11, 'valign': 'vcenter', 'border':1})

            wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'center', 'border': 1})

            # === Header Rows ===
            worksheet.merge_range(0, 0, 1, 23, "Call Type wise Summary Report", title_format)
            worksheet.merge_range(3, 3, 3, 4, f'Total Field Engineer: {total_field_engineers}', header_format)
            worksheet.merge_range(3, 5, 3, 9, 'Total Calls', header_format)  
            worksheet.merge_range(3, 10, 3, 13, 'Chargeable', header_format)  
            worksheet.merge_range(3, 14, 3, 16, 'AMC', header_format)  
            worksheet.merge_range(3, 17, 3, 20, 'Warranty', header_format)  
            worksheet.merge_range(3, 21, 3, 23, 'Free', header_format)  

            # Sub-Headers
            subheaders = [
                'Week No.', 'Day', 'Date',
                'Present','Absent', 
                'Registered', 'Allocated', 'Completed', 'Pending', 'Call Avg/Eng /Day',  
                'Registered', 'Allocated', 'Completed', 'Value',  
                'Registered', 'Completed', 'Pending',  
                'Registered', 'Installation', 'Completed', 'Pending',  
                'Registered', 'Completed', 'Pending' 
            ]

            col_index = 0
            for sub in subheaders:
                worksheet.write(4, col_index, sub, subheader_format)
                col_index += 1

            worksheet.write(3, 0, '', empty_format)
            worksheet.write(3, 1, '', empty_format)
            worksheet.write(3, 2, '', empty_format)

            # === Data Rows ===
            rows_by_week = defaultdict(list)
            totals = [0] * len(subheaders)  

            if not data_by_date:
                total_row_idx = 6
                worksheet.merge_range(total_row_idx, 0, total_row_idx, 2, 'Total', empty_format)
                for col_idx in range(3, len(subheaders)):
                    worksheet.write(total_row_idx, col_idx, 0, empty_format)

                worksheet.set_column(0, len(subheaders) + 1, 15)
                workbook.close()
                output.seek(0)
                response = request.make_response(output.read(),
                                                 headers=[('Content-Type',
                                                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                                                          ('Content-Disposition',
                                                           'attachment; filename=Call_Type_Summary_Report.xlsx')])
                return response

            for row, (date, data) in enumerate(sorted(data_by_date.items()), start=5):
                days_diff = (date - start_date.date()).days
                week_no = (days_diff // 7) + 1
                day_name = date.strftime('%A')

                call_avg_eng_day = 0
                present = data['field_engineer']['present']
                completed = data['total']['completed']
                if present > 0:
                    call_avg_eng_day = completed / present

                row_data = [
                    week_no, day_name, date.strftime('%d/%m/%Y'),
                    data['field_engineer']['present'],
                    data['field_engineer']['absent'],

                    data['total']['registered'],
                    data['total']['allocated'],
                    data['total']['completed'],
                    data['total']['pending'],
                    f"{call_avg_eng_day:.2f}",

                    data['chargeable']['registered'],
                    data['chargeable']['allocated'],
                    data['chargeable']['completed'],
                    f"{data['chargeable']['value']:.2f}",

                    data['amc']['registered'],
                    data['amc']['completed'],
                    data['amc']['pending'],

                    data['warranty']['registered'],
                    data['warranty']['installation'],
                    data['warranty']['completed'],
                    data['warranty']['pending'],

                    data['free']['registered'],
                    data['free']['completed'],
                    data['free']['pending'],
                ]

                for i, val in enumerate(row_data):
                    if i < 3:
                        continue
                    try:
                        totals[i] += float(val)
                    except Exception:
                        pass

                rows_by_week[week_no].append((row, row_data))

            # === Write data and merge week_no cells ===
            for week_no, rows in rows_by_week.items():
                first_row = rows[0][0]
                last_row = rows[-1][0]

                if last_row > first_row:
                    worksheet.merge_range(first_row, 0, last_row, 0, week_no, wrap_format)
                else:
                    worksheet.write(first_row, 0, week_no, wrap_format)

                for row_num, row_data in rows:
                    for col, val in enumerate(row_data):
                        if col == 0:
                            continue
                        worksheet.write(row_num, col, val, wrap_format)

            # === Write Total row ===
            total_row_idx = max(row for rows in rows_by_week.values() for row, _ in rows) + 1
            worksheet.merge_range(total_row_idx, 0, total_row_idx, 2, 'Total',empty_format)

            for col_idx in range(3, len(subheaders)):
                val = totals[col_idx]
                if isinstance(val, float) and val.is_integer():
                    val = int(val)
                else:
                    val = round(val, 2)
                worksheet.write(total_row_idx, col_idx, val, empty_format)

            # Auto column width
            worksheet.set_column(0, len(subheaders) + 1, 15)

            workbook.close()
            output.seek(0)

            return request.make_response(
                output.read(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', 'attachment; filename=Call_Type_wise_summary_report.xlsx'),
                ]
            )

        except Exception as e:
            _logger.error("Excel generation failed: %s", e)
            return request.make_response(
                'Internal Server Error',
                headers=[('Content-Type', 'text/plain')],
                status=500
            )
