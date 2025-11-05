import base64
import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api, tools, http
from odoo.http import request
from datetime import datetime
import io
import xlsxwriter


class ServiceCall(models.Model):
    _name = 'service.call.count'
    _inherit = 'report.project.task.user'
    _description = "service call Count"
    _auto = False

    name = fields.Char(string="Call Title")
    # active = fields.Boolean(string="Active", default=True)

    ticket_id = fields.Char(string="Ticket ID")
    planned_date = fields.Datetime(string="Planned Date/Time")
    product_id = fields.Many2one('customer.product.mapping', string="Product Name")
    machine_no = fields.Many2one('stock.lot', string="Machine No")
    call_type = fields.Many2one(comodel_name='call.type', string="Call Type")
    call_sub_type = fields.Char(string="Call Sub Type")
    service_type = fields.Many2one('service.type', string="Service Type")
    call_coordinator = fields.Many2one('res.partner', string="Call Coordinator")
    coordinator_number = fields.Char(string="Coordinator Number")
    problem_solution = fields.Text(string="Problem Solution")
    create_uid = fields.Many2one('res.users', string="Call Creator")
    create_date = fields.Datetime(string="Creation Date-Time")
    reopen_count = fields.Integer(string="Re-open Count")
    reopen_reason = fields.Text(string="Re-open Reason")
    plan_on_time = fields.Selection([('yes', 'Yes'), ('no', 'No')], compute='_compute_plan_on_time',
                                    string="On-Time-Plan")
    start_on_time = fields.Selection([('yes', 'Yes'), ('no', 'No')], compute='_compute_start_on_time',
                                     string="On Time Check-In")
    response_gap = fields.Float(string="Response Gap (Hours)", compute="_compute_response_gap")
    assign_date = fields.Datetime(string="Assign Date")
    department_id = fields.Many2one('hr.department', string="Department")
    checkin_time = fields.Datetime(string="Check-In Time", compute="_compute_checkin_checkout")
    checkout_time = fields.Datetime(string="Check-Out Time", compute="_compute_checkin_checkout")
    custom_timesheet_ids = fields.One2many('account.analytic.line', 'task_id', string="Custom Timesheets")
    total_duration_hours = fields.Float(string="Total Duration (Hours)", compute="_compute_checkin_checkout")
    # timesheet_group_id = fields.One2many('account.analytic.line','task_id',string="Timesheet Group" )

    product_categ_id = fields.Many2one(related="product_id.product_category", string="Product Category")
    done_stage_change_date = fields.Datetime(
        string="Complete Date",
        compute="_compute_done_stage_change_date"
    )

    @api.depends('stage_id', 'date_last_stage_update')
    def _compute_done_stage_change_date(self):
        for rec in self:
            if rec.stage_id and rec.stage_id.name.lower() == 'done':
                rec.done_stage_change_date = rec.date_last_stage_update
            else:
                rec.done_stage_change_date = False

    @api.depends('custom_timesheet_ids')
    def _compute_checkin_checkout(self):
        for rec in self:
            if rec.custom_timesheet_ids:
                sorted_lines = sorted(
                    rec.custom_timesheet_ids,
                    key=lambda x: x.date_time or datetime.min
                )
                rec.checkin_time = sorted_lines[0].date_time or False

                sorted_lines = sorted(
                    rec.custom_timesheet_ids,
                    key=lambda x: x.end_date_time or datetime.min,
                    reverse=True
                )
                rec.checkout_time = sorted_lines[0].end_date_time or False

                if rec.checkin_time and rec.checkout_time:
                    delta = rec.checkout_time - rec.checkin_time
                    rec.total_duration_hours = delta.total_seconds() / 3600.0
                else:
                    rec.total_duration_hours = 0.0
            else:
                rec.checkin_time = False
                rec.checkout_time = False
                rec.total_duration_hours = 0.0

    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    time_to_resolve = fields.Float(
        string="Time to Resolve (Hours)",
        compute="_compute_time_to_resolve"
    )

    @api.depends('create_date', 'done_stage_change_date')
    def _compute_time_to_resolve(self):
        for rec in self:
            if rec.done_stage_change_date and rec.create_date:
                delta = rec.done_stage_change_date - rec.create_date
                rec.time_to_resolve = delta.total_seconds() / 3600.0
            else:
                rec.time_to_resolve = 0.0

    @api.depends('assign_date', 'planned_date')
    def _compute_plan_on_time(self):
        for rec in self:
            if rec.assign_date and rec.planned_date:
                delta = rec.assign_date - rec.planned_date
                rec.plan_on_time = 'yes' if abs(delta.total_seconds()) <= 1800 else 'no'
            else:
                rec.plan_on_time = 'no'

    @api.depends('checkin_time', 'planned_date')
    def _compute_start_on_time(self):
        for rec in self:
            if rec.checkin_time and rec.planned_date:
                checkin_date = rec.checkin_time.date()
                planned_date = rec.planned_date.date()
                rec.start_on_time = 'yes' if checkin_date == planned_date else 'no'
            else:
                rec.start_on_time = 'no'

    @api.depends('checkin_time', 'assign_date')
    def _compute_response_gap(self):
        for rec in self:
            if rec.checkin_time and rec.assign_date:
                checkin_date = rec.checkin_time.date()
                assign_date = rec.assign_date.date()
                delta = checkin_date - assign_date
                rec.response_gap = delta.days * 24
            else:
                rec.response_gap = 0.0

    def _select(self):
        return super()._select() + """,
            t.department_id as department_id,
            t.date_deadline as planned_date,
            t.customer_product_id as product_id,
            t.serial_number as machine_no,
            ct.id as call_type,
            t.call_sub_types as call_sub_type,
            
            t.service_types as service_type,
            t.call_coordinator_id as call_coordinator,
            t.call_coordinator_phone as coordinator_number,
            t.fix_description as problem_solution,
            t.create_uid as create_uid,
            t.reopen_count as reopen_count,
            t.reopen_reason as reopen_reason,
            t.date_assign as assign_date,
            t.sequence_fsm as ticket_id
        
        """

    def _group_by(self):
        return super()._group_by() + """,
            t.department_id,
            t.date_deadline,
            t.customer_product_id,
            t.serial_number,
            ct.id,
            t.service_types,
            t.call_coordinator_id,
            t.call_coordinator_phone,
            t.fix_description,
            t.create_uid,
            t.reopen_count,
            t.reopen_reason,
            t.date_assign,
            t.sequence_fsm,
            t.call_sub_types
          
        """

    def _from(self):
        return super()._from() + """
                INNER JOIN project_project pp
                    ON pp.id = t.project_id
                    AND pp.is_fsm = 'true'
                LEFT JOIN account_analytic_line ts ON ts.task_id = t.id
                LEFT JOIN call_type ct ON ct.id = t.call_type
                """

    @api.model
    def export_service_call_report(self):
        active_ids = request.env.context.get('active_ids') or []
        calls = request.env['service.call.count'].browse(active_ids)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Service Calls')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#ADD8E6',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        col_widths = []

        headers = [
            'Call Title', 'Ticket ID', 'Planned Date', 'Product Name', 'Machine No',
            'Call Type', 'Call Sub Type', 'Service Type', 'Call Coordinator', 'Coordinator Number',
            'Problem Solution', 'Call Creator', 'Creation Date-Time', 'Re-open Count',
            'Re-open Reason', 'On-Time-Plan', 'On-Time Check-In', 'Response Gap (Hours)',
            'Assign Date', 'Department', 'Check-In Time', 'Check-Out Time',
            'Total Duration (Hours)', 'Timesheet Description', 'Timesheet Hours', 'Timesheet Date',
            'Product Category', 'Complete Date', 'Time to Resolve'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            col_widths.append(len(header))

        row = 1
        for call in calls:
            timesheets = call.custom_timesheet_ids or self.env['account.analytic.line']
            if not timesheets:
                timesheets = [None]

            for ts in timesheets:
                values = [
                    call.name or '',
                    call.ticket_id or '',
                    str(call.planned_date or ''),
                    call.product_id.display_name or '',
                    call.machine_no.name or '',
                    call.call_type.name or '',
                    call.call_sub_type or '',
                    call.service_type.name or '',
                    call.call_coordinator.name or '',
                    call.coordinator_number or '',
                    call.problem_solution or '',
                    call.create_uid.name or '',
                    str(call.create_date or ''),
                    call.reopen_count or 0,
                    call.reopen_reason or '',
                    call.plan_on_time or '',
                    call.start_on_time or '',
                    call.response_gap or 0.0,
                    str(call.assign_date or ''),
                    call.department_id.name or '',
                    str(call.checkin_time or ''),
                    str(call.checkout_time or ''),
                    call.total_duration_hours or 0.0,
                    ts.name if ts else '',
                    ts.unit_amount if ts else 0.0,
                    str(ts.date) if ts and ts.date else '',
                    call.product_categ_id.name or '',
                    str(call.done_stage_change_date or ''),
                    call.time_to_resolve or 0.0,
                ]

                for col, val in enumerate(values):
                    worksheet.write(row, col, val)
                    val_str = str(val)
                    if len(val_str) > col_widths[col]:
                        col_widths[col] = len(val_str)

                row += 1

        for col, width in enumerate(col_widths):
            worksheet.set_column(col, col, width + 2)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'service_call_report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'service.call.count',
            'res_id': self.ids[0] if self else False,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
