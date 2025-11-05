from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import xlsxwriter
import base64


class CustomerAssignment(models.Model):
    _name = 'customer.assignment'
    _description = 'Customer Assignment'

    customer_class_filter = fields.Many2many('customer.class', 'customer_assignment_class_rel', 'assignment_id',
                                             'class_id', string='Customer Class')
    brand_filter = fields.Many2many('product.brand', 'customer_assignment_brand_rel', 'assignment_id', 'brand_id',
                                    string='Brand')
    state_filter = fields.Many2many('res.country.state', 'customer_assignment_state_rel', 'assignment_id', 'state_id',
                                    string='State')
    city_filter = fields.Many2many('res.city', 'customer_assignment_city_rel', 'assignment_id', 'city_id',
                                   string='City')
    department_filter = fields.Many2many('hr.department', 'customer_assignment_dept_rel', 'assignment_id',
                                         'department_id', string='Department')
    state_filter_emp = fields.Many2many('res.country.state', 'customer_assignment_emp_state_rel', 'assignment_id',
                                        'state_id', string='State')
    city_filter_emp = fields.Many2many('res.city', 'customer_assignment_emp_city_rel', 'assignment_id', 'city_id',
                                       string='City')
    name = fields.Char(string='Assignment Name', store=True)
    customer_ids = fields.Many2many('res.partner', 'customer_assignment_partner_rel', 'assignment_id', 'partner_id',
                                    string='Customers', domain=[('parent_id', '=', False)],
                                    context={'show_customer_address': True})
    employee_ids = fields.Many2many('hr.employee', 'customer_assignment_employee_rel', 'assignment_id', 'employee_ids',
                                    string='Employees')
    customer_count = fields.Integer(string='Customer Count', compute='_compute_counts')
    employee_count = fields.Integer(string='Employee Count', compute='_compute_counts')
    assignment_line_ids = fields.One2many('customer.assignment.line', 'assignment_id', string='Assignment Lines')

    def _get_customer_domain(self):
        """Always apply employee access domain, even for new unsaved records"""
        self.ensure_one()
        domain = [('parent_id', '=', False)]
        if self.customer_class_filter:
            domain.append(('customer_class_id', 'in', self.customer_class_filter.ids))
        if self.brand_filter:
            domain.append(('brand_id', 'in', self.brand_filter.ids))
        if self.state_filter:
            domain.append(('state_id', 'in', self.state_filter.ids))
        if self.city_filter:
            domain.append(('city_id', 'in', self.city_filter.ids))
        return domain

    def _get_employee_domain(self):
        """Build domain based on selected employee filters"""
        domain = [('active', '=', True)]
        if self.department_filter:
            domain.append(('department_id', 'in', self.department_filter.ids))
        if self.state_filter_emp:
            domain.append(('private_state_id', 'in', self.state_filter_emp.ids))
        if self.city_filter_emp:
            city_names = self.city_filter_emp.mapped('name')
            if city_names:
                domain.append(('private_city', 'in', city_names))
        return domain

    def action_apply_customer_filters(self):
        """Apply customer filters and show notification"""
        self.ensure_one()
        self.customer_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Filters Applied',
                'message': 'Customer dropdown now shows only matching records.',
                'type': 'success',
                'sticky': False}}

    def action_apply_employee_filters(self):
        """Apply employee filters and show notification"""
        self.ensure_one()
        self.employee_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Filters Applied',
                'message': 'Employee dropdown now shows only matching records.',
                'type': 'success',
                'sticky': False}}

    def action_clear_customer_filters(self):
        """Clear all customer filters and reset to show all customers"""
        self.ensure_one()
        self.write({
            'customer_class_filter': [(5, 0, 0)],
            'brand_filter': [(5, 0, 0)],
            'state_filter': [(5, 0, 0)],
            'city_filter': [(5, 0, 0)],
            'customer_ids': [(5, 0, 0)]})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Filters Cleared',
                'message': 'All filters cleared! Showing all customers.',
                'type': 'info',
                'sticky': False}}

    def action_clear_employee_filters(self):
        """Clear all customer filters and reset to show all customers"""
        self.ensure_one()
        self.write({
            'department_filter': [(5, 0, 0)],
            'state_filter_emp': [(5, 0, 0)],
            'city_filter_emp': [(5, 0, 0)],
            'employee_ids': [(5, 0, 0)]})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Filters Cleared',
                'message': 'All filters cleared! Showing all employees.',
                'type': 'info',
                'sticky': False}}

    @api.onchange('customer_class_filter', 'brand_filter', 'state_filter', 'city_filter')
    def _onchange_customer_filters(self):
        """Auto-apply customer filters when they change"""
        domain = self._get_customer_domain()
        if self.customer_ids:
            try:
                matching_customers = self.env['res.partner'].search(
                    [('id', 'in', self.customer_ids.ids)] + domain[3:])
                if len(matching_customers) != len(self.customer_ids):
                    self.customer_ids = [(5, 0, 0)]
            except Exception:
                self.customer_ids = [(5, 0, 0)]
        return {'domain': {'customer_ids': domain}}

    @api.onchange('department_filter', 'state_filter_emp', 'city_filter_emp')
    def _onchange_employee_filters(self):
        """Auto-apply employee filters when they change"""
        domain = self._get_employee_domain()
        if self.employee_ids:
            matching_employees = self.env['hr.employee'].search([('id', 'in', self.employee_ids.ids)] + domain[1:])
            if len(matching_employees) != len(self.employee_ids):
                self.employee_ids = [(5, 0, 0)]
        return {'domain': {'employee_ids': domain}}

    @api.depends('customer_ids', 'employee_ids')
    def _compute_counts(self):
        """Compute customer and employee counts"""
        for record in self:
            record.customer_count = len(record.customer_ids)
            record.employee_count = len(record.employee_ids)

    def action_add_employees(self):
        """Open wizard to add multiple employees"""
        return {
            'name': 'Add Employees',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'tree',
            'domain': [('id', 'not in', self.employee_ids.ids)],
            'target': 'new'}

    def action_remove_all_clients(self):
        """Remove all clients from assignment"""
        self.customer_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'message': 'All customers removed successfully!',
                'type': 'info'}}

    def action_view_customers(self):
        """View selected customers (blank if none selected)"""
        self.ensure_one()
        if not self.customer_ids:
            raise UserError("No customers found for this assignment.")
        domain = [('id', 'in', self.customer_ids.ids)]
        return {
            'name': 'Selected Customers',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'create': False,
                'edit': False,
                'from_assignment': True},
            'target': 'current'}

    def action_view_employees(self):
        """View assigned employees (blank if none selected)"""
        self.ensure_one()
        if not self.customer_ids:
            raise UserError("No employees found for this assignment.")
        domain = [('id', 'in', self.employee_ids.ids)] if self.employee_ids else [('id', '=', 0)]
        return {
            'name': 'Assigned Employees',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'create': False,
                'edit': False,
                'from_assignment': True},
            'target': 'current'}

    def action_export_excel(self):
        """Export assignments to Excel with automatic download"""
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        customer_sheet = workbook.add_worksheet('Customers')
        employee_sheet = workbook.add_worksheet('Employees')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        customer_headers = ['Name', 'Email', 'Phone', 'Address']
        for col, header in enumerate(customer_headers):
            customer_sheet.write(0, col, header, header_format)
        employee_headers = ['Name', 'Email', 'Phone', 'Department', 'Job Title']
        for col, header in enumerate(employee_headers):
            employee_sheet.write(0, col, header, header_format)
        assignment_lines = self.assignment_line_ids
        customer_ids = assignment_lines.mapped('client_id').ids
        employee_ids = assignment_lines.mapped('assignee_name').ids
        customers = self.env['res.partner'].browse(customer_ids)
        for row, customer in enumerate(customers, start=1):
            customer_sheet.write(row, 0, customer.name or '')
            customer_sheet.write(row, 1, customer.email or '')
            customer_sheet.write(row, 2, customer.phone or '')
            customer_sheet.write(row, 3, customer.street or '')
        employees = self.env['hr.employee'].browse(employee_ids)
        for row, employee in enumerate(employees, start=1):
            employee_sheet.write(row, 0, employee.name or '')
            employee_sheet.write(row, 1, employee.work_email or '')
            employee_sheet.write(row, 2, employee.work_phone or '')
            employee_sheet.write(row, 3, employee.department_id.name if employee.department_id else '')
            employee_sheet.write(row, 4, employee.job_id.name if employee.job_id else '')
        customer_sheet.set_column(0, 0, 25)
        customer_sheet.set_column(1, 1, 30)
        customer_sheet.set_column(2, 2, 20)
        customer_sheet.set_column(3, 3, 40)
        employee_sheet.set_column(0, 0, 25)
        employee_sheet.set_column(1, 1, 30)
        employee_sheet.set_column(2, 2, 20)
        employee_sheet.set_column(3, 3, 25)
        employee_sheet.set_column(4, 4, 25)
        workbook.close()
        output.seek(0)
        file_data = output.read()
        output.close()
        file_base64 = base64.b64encode(file_data)
        filename = f'assignments_export_{self.env.user.name}_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_base64,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
            'close': True}

    def action_clear_all(self):
        """Clear all assignments and lines"""
        self.ensure_one()
        self.assignment_line_ids.unlink()
        self.customer_ids = [(5, 0, 0)]
        self.employee_ids = [(5, 0, 0)]
        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'All assignments cleared successfully!',
                'type': 'rainbow_man'}}

    def action_delete_assignment(self):
        """Delete assignment with confirmation"""
        assignment_name = self.name
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'message': f'Assignment "{assignment_name}" deleted successfully!',
                'type': 'success'}}

    def open_customer_selector(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'customer_assignment.open_selector',
            'params': {
                'model': 'res.partner',
                'domain': [('is_company', '=', True)],
                'selected': self.customer_ids.ids,
                'title': 'Select Customers',
                'target_field': 'customer_ids',
                'res_id': self.id}}

    def open_employee_selector(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'customer_assignment.open_selector',
            'params': {
                'model': 'hr.employee',
                'domain': [],
                'selected': self.employee_ids.ids,
                'title': 'Select Employees',
                'target_field': 'employee_ids',
                'res_id': self.id}}

    def action_add_to_list(self):
        """Create assignment lines grouped by customer with comma-separated employees"""
        self.ensure_one()
        if not self.employee_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'Please select at least one employee before adding to the list!',
                    'type': 'warning',
                    'sticky': False}}
        if not self.customer_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'Please select at least one customer before adding to the list!',
                    'type': 'warning',
                    'sticky': False}}
        max_sequence = 0
        if self.assignment_line_ids:
            max_sequence = max(self.assignment_line_ids.mapped('sequence')) or 0
        customers = self.env['res.partner'].browse(self.customer_ids.ids)
        employees = self.env['hr.employee'].browse(self.employee_ids.ids)
        customer_assignments = {}
        for customer in customers:
            if customer not in customer_assignments:
                customer_assignments[customer] = self.env['hr.employee']
            customer_assignments[customer] |= employees
        for customer, employees in customer_assignments.items():
            existing_line = self.env['customer.assignment.line'].search([
                ('assignment_id', '=', self.id),
                ('client_id', '=', customer.id)], limit=1)  # Search by client_id instead of client_names
            if existing_line:
                all_employees = existing_line.assignee_name | employees
                existing_line.write({
                    'client_names': customer.id,  # Use customer ID instead of string
                    'assignee_name': [(6, 0, all_employees.ids)]})
            else:
                max_sequence += 1
                self.env['customer.assignment.line'].create({
                    'assignment_id': self.id,
                    'sequence': max_sequence,
                    'client_names': customer.id,  # Use customer ID instead of string
                    'client_id': customer.id,
                    'assignee_name': [(6, 0, employees.ids)]})
        self.write({
            'customer_ids': [(5, 0, 0)],
            'employee_ids': [(5, 0, 0)]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Assignments updated successfully!',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload'}}}

    def _format_customer_name_with_address(self, customer):
        """Helper method to format customer name with address"""
        name = customer.name or ''
        address_parts = []
        if customer.street:
            address_parts.append(customer.street)
        if customer.street2:
            address_parts.append(customer.street2)
        if customer.city:
            address_parts.append(customer.city)
        if customer.state_id:
            address_parts.append(customer.state_id.name)
        if customer.zip:
            address_parts.append(customer.zip)
        if address_parts:
            address = ', '.join(address_parts)
            return f"{name} - {address}"
        else:
            return name

    def action_edit_line(self, line_id):
        """Edit a specific assignment line"""
        return {
            'name': 'Edit Assignment',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.assignment.line',
            'res_id': line_id,
            'view_mode': 'form',
            'target': 'new'}

    def action_delete_line(self, line_id):
        """Delete a specific assignment line"""
        line = self.env['customer.assignment.line'].browse(line_id)
        line.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'message': 'Assignment line deleted!',
                'type': 'warning'}}

    #########################################################################################
    def action_view_customers_in_lines(self):
        """Open custom view of customers and their employees"""
        report_model = self.env['customer.employee.report']
        report_model.generate_report_lines()
        return {
            'name': 'Customers with Assigned Employees',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.employee.report',
            'view_mode': 'tree,form',
            'target': 'current'}

    def action_view_employees_in_lines(self):
        """Open custom view of employees and their customers"""
        report_model = self.env['employee.customer.report']
        report_model.generate_report_lines()
        return {
            'name': 'Employees with Assigned Customers',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.customer.report',
            'view_mode': 'tree,form',
            'target': 'current'}


class CustomerAssignmentLine(models.Model):
    _name = 'customer.assignment.line'
    _description = 'Customer Assignment Line'
    _order = 'sequence, id'

    sequence = fields.Integer()
    assignment_id = fields.Many2one('customer.assignment', string='Assignment', ondelete='cascade')
    client_names = fields.Many2one('res.partner', string='Customers Name')
    client_id = fields.Many2one('res.partner', string='Customer')
    assignee_name = fields.Many2many('hr.employee')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            args += assignment._get_customer_domain()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        domain = domain or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            domain += assignment._get_customer_domain()
        return super().search_read(domain, fields, offset, limit, order)

    @api.model
    def web_search_read(self, domain=None, *args, **kwargs):
        domain = domain or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            domain += assignment._get_customer_domain()
        # Check if we're in customer assignment context and add show_customer_address
        context = self.env.context.copy()
        if assignment_id or self.env.context.get('show_customer_address'):
            context['show_customer_address'] = True
        return super(ResPartner, self).web_search_read(domain, *args, **kwargs)


class CustomerEmployeeReport(models.Model):
    _name = "customer.employee.report"
    _description = "Customer and their Assigned Employees"

    customer_id = fields.Many2one("res.partner", string="Customer")
    employee_names = fields.Many2many("hr.employee", string="Employees")
    create_new_customer = fields.Boolean(string="Create New Customer")
    new_customer_name = fields.Char(string="New Customer Name")
    assignment_id = fields.Many2many('customer.assignment', string='Select Assignments',
                                     help="Select assignments to view")

    @api.model
    def create(self, vals):
        if vals.get('create_new_customer') and vals.get('new_customer_name'):
            new_customer = self.env['res.partner'].create({
                'name': vals['new_customer_name'],
                'company_type': 'company',
            })
            vals['customer_id'] = new_customer.id
        ass_ids = []
        for cmd in vals.get('assignment_id', []):
            if cmd[0] == 6:
                ass_ids = cmd[2]
            elif cmd[0] == 4:
                ass_ids.append(cmd[1])
        # Clean temp fields
        vals.pop('create_new_customer', None)
        vals.pop('new_customer_name', None)
        rec = super().create(vals)
        # ✅ Only update selected assignments. No fallback!
        if ass_ids and rec.customer_id and rec.employee_names:
            assignments = self.env['customer.assignment'].browse(ass_ids)
            for assignment in assignments:
                line = self.env['customer.assignment.line'].search([
                    ('client_names', '=', rec.customer_id.id),
                    ('assignment_id', '=', assignment.id),
                ], limit=1)
                if line:
                    line.write({'assignee_name': [(6, 0, rec.employee_names.ids)]})
                else:
                    max_sequence_line = self.env['customer.assignment.line'].search(
                        [('assignment_id', '=', assignment.id)],
                        order='sequence desc', limit=1)
                    next_seq = max_sequence_line.sequence + 1 if max_sequence_line else 10
                    self.env['customer.assignment.line'].create({
                        'assignment_id': assignment.id,
                        "client_names": rec.customer_id.id,
                        'client_id': rec.customer_id.id,
                        'assignee_name': [(6, 0, rec.employee_names.ids)],
                        'sequence': next_seq})
        return rec

    def _get_customer_assignments(self, customer_id):
        """Get all assignments where this customer appears"""
        return self.env['customer.assignment'].search([
            ('assignment_line_ids.client_id', '=', customer_id)])

    @api.model
    def generate_report_lines(self):
        self.search([]).unlink()
        lines = self.env['customer.assignment.line'].search([])
        result = {}
        for line in lines:
            cust = line.client_id
            if not cust:
                continue
            if cust.id not in result:
                result[cust.id] = set()
            result[cust.id].update(line.assignee_name.ids)
        for cust_id, employee_ids in result.items():
            self.create({
                'customer_id': cust_id,
                'employee_names': [(6, 0, list(employee_ids))]})
        return self.search([])

    def write(self, vals):
        res = super().write(vals)
        if 'employee_names' in vals or 'assignment_id' in vals:
            for rec in self:
                ass_ids = rec.assignment_id.ids
                if not ass_ids or not rec.customer_id:
                    continue
                assignments = self.env['customer.assignment'].browse(ass_ids)
                for assignment in assignments:
                    line = self.env['customer.assignment.line'].search([
                        ('client_id', '=', rec.customer_id.id),
                        ('assignment_id', '=', assignment.id)], limit=1)
                    if line:
                        line.write({'assignee_name': [(6, 0, rec.employee_names.ids)]})
                    else:
                        existing_line = self.env['customer.assignment.line'].search(
                            [('assignment_id', '=', assignment.id)],
                            order='sequence desc', limit=1)
                        next_seq = (existing_line.sequence + 1) if existing_line else 0
                        self.env['customer.assignment.line'].create({
                            'assignment_id': assignment.id,
                            'client_id': rec.customer_id.id,
                            "client_names": rec.customer_id.id,
                            'assignee_name': [(6, 0, rec.employee_names.ids)],
                            'sequence': next_seq})
        return res

    def _get_current_assignments(self):
        """Get assignments where this customer appears"""
        return self.env['customer.assignment'].search([
            ('assignment_line_ids.client_id', '=', self.customer_id.id)])


class EmployeeCustomerReport(models.Model):
    _name = "employee.customer.report"
    _description = "Employee and their Assigned Customers"

    employee_id = fields.Many2one("hr.employee", string="Employee")
    customer_names = fields.Many2many("res.partner", string="Customers", domain=[('parent_id', '=', False)])
    create_new_employee = fields.Boolean(string="Create New Employee")
    new_employee_name = fields.Char(string="New Employee Name")
    assignment_id = fields.Many2many('customer.assignment', string='Select Assignments',
                                     help="Select assignments to view")

    def _get_assignment_to_use(self):
        """Get the assignment to use - either selected or default"""
        if self.assignment_id:
            return self.assignment_id
        return self._get_or_create_default_assignment()

    @api.model
    def create(self, vals):
        if vals.get('create_new_employee') and vals.get('new_employee_name'):
            new_employee = self.env['hr.employee'].create({
                'name': vals.get('new_employee_name')})
            vals['employee_id'] = new_employee.id
        temp_vals = vals.copy()
        temp_vals.pop('create_new_employee', None)
        temp_vals.pop('new_employee_name', None)
        record = super(EmployeeCustomerReport, self).create(temp_vals)
        if record.employee_id and record.customer_names:
            assignment = self._get_assignment_to_use()
            for customer in record.customer_names:
                existing_line = self.env["customer.assignment.line"].search([
                    ("client_id", "=", customer.id),
                    ("assignment_id", "=", assignment.id),
                ], limit=1)
                if existing_line:
                    if record.employee_id.id not in existing_line.assignee_name.ids:
                        existing_line.write({
                            "assignee_name": [(4, record.employee_id.id)]})
                else:
                    max_sequence = self.env["customer.assignment.line"].search([
                        ("assignment_id", "=", assignment.id)], order="sequence desc", limit=1)
                    next_sequence = (max_sequence.sequence + 1) if max_sequence else 10
                    self.env["customer.assignment.line"].create({
                        "assignment_id": assignment.id,
                        "client_id": customer.id,
                        "client_names": customer.id,
                        "assignee_name": [(4, record.employee_id.id)],
                        "sequence": next_sequence})
        return record

    def _get_or_create_default_assignment(self):
        """Get existing assignment or create a default one"""
        assignment = self.env['customer.assignment'].search([], limit=1)
        if not assignment:
            assignment = self.env['customer.assignment'].create({
                'name': 'Default Assignment'})
        return assignment

    @api.model
    def generate_report_lines(self, assignment_ids=False):
        self.search([]).unlink()
        domain = []
        if assignment_ids:
            domain = [('assignment_id', 'in', assignment_ids)]
        lines = self.env['customer.assignment.line'].search(domain)
        result = {}
        for line in lines:
            if not line.assignee_name or not line.client_id:
                continue
            for emp in line.assignee_name:
                if emp.id not in result:
                    result[emp.id] = {
                        'customers': set(),
                        'assignments': set()
                    }
                result[emp.id]['customers'].add(line.client_id.id)
                result[emp.id]['assignments'].add(line.assignment_id.id)
        for emp_id, data in result.items():
            self.create({
                'employee_id': emp_id,
                'customer_names': [(6, 0, list(data['customers']))],
                'assignment_id': [(6, 0, list(data['assignments']))]
            })
        return self.search([])

    def write(self, vals):
        for rec in self:
            if "customer_names" in vals:
                old_customers = set(rec.customer_names.ids)
                commands = vals.get("customer_names")
                new_customers = set(old_customers)
                for command in commands:
                    if command[0] == 6:
                        new_customers = set(command[2])
                    elif command[0] == 4:
                        new_customers.add(command[1])
                    elif command[0] == 3:
                        new_customers.discard(command[1])
                removed_customers = old_customers - new_customers
                added_customers = new_customers - old_customers
                assignments = rec._get_assignment_to_use()
                if removed_customers:
                    for assignment in assignments:
                        assignment_lines = self.env["customer.assignment.line"].search([
                            ("client_id", "in", list(removed_customers)),
                            ("assignee_name", "in", [rec.employee_id.id]),
                            ("assignment_id", "=", assignment.id)
                        ])
                        for line in assignment_lines:
                            if len(line.assignee_name) > 1:
                                line.write({
                                    "assignee_name": [(3, rec.employee_id.id)]
                                })
                            else:
                                line.unlink()
                if added_customers:
                    for assignment in assignments:
                        for cust_id in added_customers:
                            customer = self.env['res.partner'].browse(cust_id)
                            existing_line = self.env["customer.assignment.line"].search([
                                ("client_id", "=", cust_id),
                                ("assignment_id", "=", assignment.id)
                            ], limit=1)
                            if existing_line:
                                if rec.employee_id.id not in existing_line.assignee_name.ids:
                                    existing_line.write({
                                        "assignee_name": [(4, rec.employee_id.id)]
                                    })
                            else:
                                max_sequence = self.env["customer.assignment.line"].search([
                                    ("assignment_id", "=", assignment.id)], order="sequence desc", limit=1)
                                next_sequence = (max_sequence.sequence + 1) if max_sequence else 0
                                self.env["customer.assignment.line"].create({
                                    "assignment_id": assignment.id,
                                    "client_id": cust_id,
                                    "client_names": customer.id,
                                    "assignee_name": [(4, rec.employee_id.id)],
                                    "sequence": next_sequence
                                })
        return super(EmployeeCustomerReport, self).write(vals)
