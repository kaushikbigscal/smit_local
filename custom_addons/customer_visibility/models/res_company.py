from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, MissingError, AccessError
from odoo.osv import expression


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    state_id = fields.Many2one("res.country.state", string="State", related="address_id.state_id", store=True)
    city = fields.Char(string="City", related="address_id.city", store=True)
    customer_access_scope = fields.Selection(
        [('all', 'All'), ('self', 'Self'), ('assigned', 'Assigned'), ('select', 'Select')],
        string="Customer Access Scope", default='self', required=True)
    allowed_customer_ids = fields.Many2many('res.partner', 'employee_customer_rel', 'employee_id', 'customer_id',
                                            string="Allowed Customers")
    has_user = fields.Boolean(string="Has User Account", compute='_compute_has_user', store=True)
    # Location Restrictions
    restrict_by_location = fields.Boolean(string="Restrict By Location", default=False,
                                          help="Enable location-based restrictions")
    location_restriction_zone = fields.Boolean(string="Zone", default=False)
    location_restriction_state = fields.Boolean(string="State", default=False)
    location_restriction_city = fields.Boolean(string="City", default=False)
    # Helper for visibility
    show_restrict_by_location = fields.Boolean(compute="_compute_show_restrict_by_location", store=True)
    show_zone_field = fields.Boolean(compute="_compute_location_flags", store=True)
    show_state_field = fields.Boolean(compute="_compute_location_flags", store=True)
    show_city_field = fields.Boolean(compute="_compute_location_flags", store=True)
    # Location Selection Fields
    allowed_zone_ids = fields.Many2many('zone.master', 'employee_zone_rel', 'employee_id', 'zone_id',
                                        string="Allowed Zones")
    # Location Selection Fields
    allowed_sub_zone_ids = fields.Many2many('sub.zone', 'employee_sub_zone_rel', 'employee_id', 'zone_master_id',
                                            string="Allowed Sub-Zones")
    allowed_state_ids = fields.Many2many('res.country.state', 'employee_state_rel', 'employee_id', 'state_id',
                                         string="Allowed States")
    allowed_city_ids = fields.Many2many('res.city', 'employee_city_rel', 'employee_id', 'city_id',
                                        string="Allowed Cities", domain="[('state_id', 'in', allowed_state_ids)]")
    # Business Restrictions
    restrict_by = fields.Boolean(string="Restrict By", default=False, help="Enable business-based restrictions")
    customer_class = fields.Boolean(string="Customer Class", default=False)
    product_brand = fields.Boolean(string="Product Brand", default=False)
    # Business Selection Fields
    allowed_customer_class_ids = fields.Many2many('customer.class', 'employee_customer_class_rel', 'employee_id',
                                                  'customer_class_id', string="Allowed Customer Classes")
    allowed_product_brand_ids = fields.Many2many('product.brand', 'employee_product_brand_rel', 'employee_id',
                                                 'brand_id', string="Allowed Product Brands")
    # Helper for visibility
    show_restrict_by = fields.Boolean(compute="_compute_show_restrict_by", store=False)
    show_class_field = fields.Boolean(compute="_compute_restrict_by_flags", store=False)
    show_brand_field = fields.Boolean(compute="_compute_restrict_by_flags", store=False)

    @api.depends('user_id')
    def _compute_has_user(self):
        for employee in self:
            employee.has_user = bool(employee.user_id)

    @api.constrains('customer_access_scope')
    def _check_restriction_flags(self):
        for employee in self:
            if employee.customer_access_scope == 'select':
                company = employee.company_id or self.env.company
                if not any([
                    company.restrict_zone,
                    company.restrict_state,
                    company.restrict_city,
                    company.restrict_customer_class,
                    company.restrict_product_brand]):
                    raise ValidationError(_(
                        "Contact your admin: All restriction flags are disabled at company level. "
                        "At least one restriction must be enabled when selecting 'Select' access scope."))

    @api.depends('customer_access_scope')
    def _compute_show_restrict_by_location(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.show_restrict_by_location = (
                    (company.restrict_zone or company.restrict_state or company.restrict_city)
                    and rec.customer_access_scope not in ['all', 'self', 'assigned'])

    @api.depends('restrict_by_location')
    def _compute_location_flags(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.show_zone_field = rec.restrict_by_location and company.restrict_zone
            rec.show_state_field = rec.restrict_by_location and company.restrict_state
            rec.show_city_field = rec.restrict_by_location and company.restrict_city

    @api.onchange('allowed_zone_ids')
    def _onchange_allowed_zone_ids(self):
        self.allowed_sub_zone_ids = [(5, 0, 0)]
        if self.allowed_zone_ids:
            return {'domain': {'allowed_sub_zone_ids': [('zone_master_id', 'in', self.allowed_zone_ids.ids)]}}
        else:
            return {'domain': {'allowed_sub_zone_ids': []}}

    @api.depends('customer_access_scope')
    def _compute_show_restrict_by(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.show_restrict_by = (
                    (company.restrict_customer_class or company.restrict_product_brand)
                    and rec.customer_access_scope not in ['all', 'self', 'assigned'])

    @api.depends('restrict_by')
    def _compute_restrict_by_flags(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.show_class_field = rec.restrict_by and company.restrict_customer_class
            rec.show_brand_field = rec.restrict_by and company.restrict_product_brand

    @api.onchange('restrict_by_location')
    def _onchange_restrict_by_location(self):
        """Clear location restrictions when disabled"""
        if not self.restrict_by_location:
            self.location_restriction_zone = False
            self.location_restriction_state = False
            self.location_restriction_city = False
            self.allowed_zone_ids = [(5, 0, 0)]
            self.allowed_state_ids = [(5, 0, 0)]
            self.allowed_city_ids = [(5, 0, 0)]

    @api.onchange('restrict_by')
    def _onchange_restrict_by(self):
        """Clear business restrictions when disabled"""
        if not self.restrict_by:
            self.customer_class = False
            self.product_brand = False
            self.allowed_customer_class_ids = [(5, 0, 0)]
            self.allowed_product_brand_ids = [(5, 0, 0)]

    @api.onchange('location_restriction_zone')
    def _onchange_location_restriction_zone(self):
        if not self.location_restriction_zone:
            self.allowed_zone_ids = [(5, 0, 0)]
            if self.user_id.partner_id:
                self.user_id.partner_id.zone_id = False

    @api.onchange('location_restriction_state')
    def _onchange_location_restriction_state(self):
        if not self.location_restriction_state:
            self.allowed_state_ids = [(5, 0, 0)]

    @api.onchange('location_restriction_city')
    def _onchange_location_restriction_city(self):
        if not self.location_restriction_city:
            self.allowed_city_ids = [(5, 0, 0)]

    @api.onchange('customer_class')
    def _onchange_customer_class(self):
        if not self.customer_class:
            self.allowed_customer_class_ids = [(5, 0, 0)]

    @api.onchange('product_brand')
    def _onchange_product_brand(self):
        if not self.product_brand:
            self.allowed_product_brand_ids = [(5, 0, 0)]

    @api.onchange('customer_access_scope')
    def _onchange_customer_access_scope(self):
        if self.customer_access_scope in ['all', 'self', 'assigned']:
            self.allowed_customer_ids = [(5, 0, 0)]
            self.restrict_by_location = False
            self.location_restriction_zone = False
            self.location_restriction_state = False
            self.location_restriction_city = False
            self.allowed_zone_ids = [(5, 0, 0)]
            self.allowed_state_ids = [(5, 0, 0)]
            self.allowed_city_ids = [(5, 0, 0)]
            self.allowed_sub_zone_ids = [(5, 0, 0)]
            self.restrict_by = False
            self.customer_class = False
            self.product_brand = False
            self.allowed_customer_class_ids = [(5, 0, 0)]
            self.allowed_product_brand_ids = [(5, 0, 0)]

    def _get_customer_domain(self):
        self.ensure_one()
        domain = []
        if self.customer_access_scope == 'self':
            domain = [('id', 'in', self.allowed_customer_ids.ids)]
        elif self.customer_access_scope == 'assigned':
            loc_domain = []
            biz_domain = []
            if self.restrict_by_location:
                if self.location_restriction_zone and self.allowed_zone_ids:
                    loc_domain.append(('zone_id', 'in', self.allowed_zone_ids.ids))
                if self.location_restriction_state and self.allowed_state_ids:
                    loc_domain.append(('state_id', 'in', self.allowed_state_ids.ids))
                if self.location_restriction_city and self.allowed_city_ids:
                    loc_domain.append(('city_id', 'in', self.allowed_city_ids.ids))
            if self.restrict_by and self.customer_class and self.allowed_customer_class_ids:
                biz_domain.append(('customer_class_id', 'in', self.allowed_customer_class_ids.ids))
            if loc_domain and biz_domain:
                domain = expression.AND([loc_domain, biz_domain])
            elif loc_domain:
                domain = loc_domain
            elif biz_domain:
                domain = biz_domain
        return domain

    def _get_employee_partner_domain(self):
        """Returns domain based on employee's restrictions"""
        self.ensure_one()
        if self.customer_access_scope == 'all':
            return [('parent_id', '=', False)]
        elif self.customer_access_scope == 'self':
            return [('customer_visibility_access', '=', self.id)]
        elif self.customer_access_scope == 'select':
            return [('id', 'in', self.allowed_customer_ids.ids)]
        elif self.customer_access_scope == 'assigned':
            domains = []
            if self.restrict_by_location:
                if self.location_restriction_zone and self.allowed_zone_ids:
                    domains.append([('zone_id', 'in', self.allowed_zone_ids.ids)])
                if self.location_restriction_state and self.allowed_state_ids:
                    domains.append([('state_id', 'in', self.allowed_state_ids.ids)])
                if self.location_restriction_city and self.allowed_city_ids:
                    domains.append([('city', 'in', [city.name for city in self.allowed_city_ids])])
            if self.restrict_by:
                if self.customer_class and self.allowed_customer_class_ids:
                    domains.append([('customer_class_id', 'in', self.allowed_customer_class_ids.ids)])
                if self.product_brand and self.allowed_product_brand_ids:
                    domains.append([('brand_id', 'in', self.allowed_product_brand_ids.ids)])
            domains.append([('parent_id', '=', False)])
            return expression.AND(domains) if domains else [('parent_id', '=', False)]
        return []

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            args += assignment._get_employee_domain()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        domain = domain or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            domain += assignment._get_employee_domain()
        return super().search_read(domain, fields, offset, limit, order)

    @api.model
    def web_search_read(self, domain=None, *args, **kwargs):
        domain = domain or []
        assignment_id = self.env.context.get('customer_assignment_id')
        if assignment_id:
            assignment = self.env['customer.assignment'].browse(assignment_id)
            domain += assignment._get_employee_domain()
        return super(HREmployee, self).web_search_read(domain, *args, **kwargs)

    @api.constrains('customer_access_scope', 'restrict_by_location', 'restrict_by')
    def _check_at_least_one_restriction_enabled(self):
        for employee in self:
            if employee.customer_access_scope == 'select':
                if not employee.restrict_by_location and not employee.restrict_by:
                    raise ValidationError(_(
                        "When Customer Access Scope is 'Select', you must enable "
                        "at least one restriction option ('Restrict By Location' or 'Restrict By')."
                    ))

    @api.constrains(
        "restrict_by_location",
        "location_restriction_zone",
        "location_restriction_state",
        "location_restriction_city",
        "restrict_by",
        "customer_class",
        "product_brand",
    )
    def _check_restriction_consistency(self):
        for employee in self:
            # --- Location Restriction ---
            if employee.restrict_by_location:
                if not any([
                    employee.location_restriction_zone,
                    employee.location_restriction_state,
                    employee.location_restriction_city
                ]):
                    raise ValidationError(_(
                        "At least one location restriction (Zone, State or City) "
                        "must be selected if Restrict by Location is enabled."
                    ))

            # --- Customer Class / Product Brand Restriction ---
            if employee.restrict_by:
                if not any([
                    employee.customer_class,
                    employee.product_brand
                ]):
                    raise ValidationError(_(
                        "At least one restriction (Customer Class or Product Brand) "
                        "must be selected if Restrict by is enabled."
                    ))


class ResCompany(models.Model):
    _inherit = 'res.company'

    restrict_zone = fields.Boolean(string="Restrict by Zone", default=False)
    restrict_state = fields.Boolean(string="Restrict by State", default=False)
    restrict_city = fields.Boolean(string="Restrict by City", default=False)
    restrict_customer_class = fields.Boolean(string="Restrict by Customer Class", default=False)
    restrict_product_brand = fields.Boolean(string="Restrict by Product Brand", default=False)

    def write(self, vals):
        res = super().write(vals)
        for company in self:
            partners = self.env['res.partner'].with_context(active_test=False).search([
                ('company_id', '=', company.id)])
            if 'restrict_customer_class' in vals and not vals['restrict_customer_class']:
                partners.write({'customer_class_id': False})
            if 'restrict_zone' in vals and not vals['restrict_zone']:
                partners.write({'zone_id': False})
            if 'restrict_product_brand' in vals and not vals['restrict_product_brand']:
                partners.write({'brand_id': False})
            employees = self.env['hr.employee'].search([('company_id', '=', company.id)])
            clear_data = {
                'restrict_zone': {'location_restriction_zone': False, 'allowed_zone_ids': [(5, 0, 0)],
                                  'allowed_sub_zone_ids': [(5, 0, 0)]},
                'restrict_state': {'location_restriction_state': False, 'allowed_state_ids': [(5, 0, 0)]},
                'restrict_city': {'location_restriction_city': False, 'allowed_city_ids': [(5, 0, 0)]},
                'restrict_customer_class': {'customer_class': False, 'allowed_customer_class_ids': [(5, 0, 0)]},
                'restrict_product_brand': {'product_brand': False, 'allowed_product_brand_ids': [(5, 0, 0)]}}
            for field, data in clear_data.items():
                if field in vals and not vals[field]:
                    employees.write(data)
            location_flags = ['restrict_zone', 'restrict_state', 'restrict_city']
            if any(flag in vals for flag in location_flags):
                if not (company.restrict_zone or company.restrict_state or company.restrict_city):
                    employees.write({
                        'restrict_by_location': False,
                        'location_restriction_zone': False,
                        'location_restriction_state': False,
                        'location_restriction_city': False,
                        'allowed_zone_ids': [(5, 0, 0)],
                        'allowed_sub_zone_ids': [(5, 0, 0)],
                        'allowed_state_ids': [(5, 0, 0)],
                        'allowed_city_ids': [(5, 0, 0)]})
            business_flags = ['restrict_customer_class', 'restrict_product_brand']
            if any(flag in vals for flag in business_flags):
                if not (company.restrict_customer_class or company.restrict_product_brand):
                    employees.write({
                        'restrict_by': False,
                        'customer_class': False,
                        'product_brand': False,
                        'allowed_customer_class_ids': [(5, 0, 0)],
                        'allowed_product_brand_ids': [(5, 0, 0)]})
        return res


class CustomerClass(models.Model):
    _name = 'customer.class'
    _description = 'Customer Class'
    _rec_name = 'name'

    name = fields.Char(string='Customer Class', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_class_id = fields.Many2one('customer.class', string='Customer Class')
    zone_id = fields.Many2one('sub.zone', string='Zone')
    brand_id = fields.Many2one('product.brand', string='Brand Name')
    created_by = fields.Many2one('hr.employee', string='Created By', default=lambda
        self: self.env.user.employee_id.id if self.env.user.employee_id else False, readonly=True)
    customer_visibility_access = fields.Many2one('hr.employee', string='Customer Visibility Access', default=lambda
        self: self.env.user.employee_id.id if self.env.user.employee_id else False)
    show_customer_class = fields.Boolean(compute='_compute_show_restriction_fields', string="Show Customer Class Field")
    show_zone = fields.Boolean(compute='_compute_show_restriction_fields', string="Show Zone Field")
    show_brand = fields.Boolean(compute='_compute_show_restriction_fields', string="Show Brand Field")

    @api.model
    def default_get(self, fields_list):
        """Set default values for customer_class_id, zone_id, and brand_id based on employee restrictions"""
        defaults = super().default_get(fields_list)

        employee = self.env.user.employee_id
        if not employee:
            return defaults

        company = self.env.company

        # Auto-populate based on employee's customer_access_scope
        if employee.customer_access_scope == 'select':
            # For 'select' scope, use employee's allowed values (first one if multiple)

            if 'customer_class_id' in fields_list and company.restrict_customer_class:
                if employee.customer_class and employee.allowed_customer_class_ids:
                    # Filter by current company
                    class_ids = employee.allowed_customer_class_ids.filtered(
                        lambda c: not c.company_id or c.company_id.id == company.id
                    )
                    if class_ids:
                        defaults['customer_class_id'] = class_ids[0].id
            if 'zone_id' in fields_list and company.restrict_zone:
                if employee.location_restriction_zone:
                    # First check if employee has sub-zones selected
                    if employee.allowed_sub_zone_ids:
                        defaults['zone_id'] = employee.allowed_sub_zone_ids[0].id
                    # If no sub-zones, get first sub-zone from employee's main zones
                    elif employee.allowed_zone_ids:
                        first_sub_zone = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ], limit=1)
                        if first_sub_zone:
                            defaults['zone_id'] = first_sub_zone.id

            if 'brand_id' in fields_list and company.restrict_product_brand:
                if employee.product_brand and employee.allowed_product_brand_ids:
                    defaults['brand_id'] = employee.allowed_product_brand_ids[0].id

        else:
            # For other scopes (all, self, assigned), use first available option from dropdown

            if 'customer_class_id' in fields_list and company.restrict_customer_class:
                first_class = self.env['customer.class'].search([], limit=1)
                if first_class:
                    defaults['customer_class_id'] = first_class.id

            if 'zone_id' in fields_list and company.restrict_zone:
                first_zone = self.env['sub.zone'].search([], limit=1)
                if first_zone:
                    defaults['zone_id'] = first_zone.id

            if 'brand_id' in fields_list and company.restrict_product_brand:
                first_brand = self.env['product.brand'].search([], limit=1)
                if first_brand:
                    defaults['brand_id'] = first_brand.id

        return defaults

    @api.model
    def _get_partner_domain(self):
        employee = self.env.user.employee_id
        domain = []
        if not employee:
            return domain

        # Get the current company from context or user
        current_company = self.env.company

        if employee.customer_access_scope == 'all':
            domain = [
                ('parent_id', '=', False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                # ('employee_ids', '=', False),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]

        elif employee.customer_access_scope == 'self':
            domain = [
                ('customer_visibility_access', '=', employee.id),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_type', '!=', 'distribution'),
                ('company_id', 'in', [False, current_company.id]),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'assigned':
            assignment_lines = self.env['customer.assignment.line'].search([
                ('assignee_name', '=', employee.id),
                ('company_id', '=', current_company.id)
            ])
            assigned_customers = assignment_lines.mapped('client_id')
            domain = [
                ('id', 'in', assigned_customers.ids),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'select':
            select_domain = []
            # Use the employee's company or current company
            company = employee.company_id or current_company

            if employee.restrict_by_location:
                # ZONE/SUB-ZONE FILTERING - SIMPLIFIED
                if company.restrict_zone and employee.location_restriction_zone:
                    zone_filter_ids = []

                    # FIRST: Check if sub-zones are selected
                    if employee.allowed_sub_zone_ids:
                        zone_filter_ids = employee.allowed_sub_zone_ids.ids
                    # SECOND: If no sub-zones selected, check main zones
                    elif employee.allowed_zone_ids:
                        # Get all sub-zones under the selected main zones
                        sub_zones_from_zones = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ])
                        zone_filter_ids = sub_zones_from_zones.ids

                    # Apply the filter if we have any zone IDs
                    if zone_filter_ids:
                        select_domain.append(('zone_id', 'in', zone_filter_ids))
                if company.restrict_state and employee.location_restriction_state and employee.allowed_state_ids:
                    select_domain.append(('state_id', 'in', employee.allowed_state_ids.ids))
                if company.restrict_city and employee.location_restriction_city and employee.allowed_city_ids:
                    if 'city_id' in self.env['res.partner']._fields:
                        select_domain.append(('city_id', 'in', employee.allowed_city_ids.ids))
                    else:
                        select_domain.append(('city', 'in', employee.allowed_city_ids.mapped('name')))

            if employee.restrict_by:
                if company.restrict_customer_class and employee.customer_class and employee.allowed_customer_class_ids:
                    select_domain.append(('customer_class_id', 'in', employee.allowed_customer_class_ids.ids))
                if company.restrict_product_brand and employee.product_brand and employee.allowed_product_brand_ids:
                    select_domain.append(('brand_id', 'in', employee.allowed_product_brand_ids.ids))

            # Final domain with company restriction
            if select_domain:
                select_domain.append(('parent_id', '=', False))
                select_domain.append(('company_id', 'in', [False, current_company.id]))
                domain = select_domain
            elif employee.allowed_customer_ids:
                domain = [
                    ('id', 'in', employee.allowed_customer_ids.ids),
                    ('parent_id', '=', False),
                    # ("employee_ids", "=", False),
                    ('company_id', 'in', [False, current_company.id]),
                    ('company_type', '!=', 'distribution'),
                    '|',
                    ('user_ids', '=', False),
                    ('user_ids.share', '=', True),
                ]
            else:
                domain = [('id', '=', False)]  # No access if no restrictions defined

        # Add company filter to ensure multi-company safety
        if not any(term[0] == 'company_id' for term in domain):
            domain.append(('company_id', 'in', [False, current_company.id]))

        # Simple exclusion: hide contacts linked to employees without users
        domain.append(('id', 'not in', self.env['hr.employee'].sudo().search([
            ('user_id', '=', False),
            ('company_id', 'in', [False, current_company.id])
        ]).mapped('work_contact_id').ids))

        return domain

    @api.model
    def action_all_customers(self):
        """Server action that applies ONLY your custom domain"""
        try:
            domain = self._get_partner_domain()
            if not domain:
                domain = [('parent_id', '=', False)]
        except Exception:
            domain = [('id', '=', False)]
        return {
            'name': 'Customers',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'custom_customer_action': True,
                'search_default_customer': False,
                'search_default_supplier': False,
            }
        }

    @api.depends('company_id.restrict_customer_class', 'company_id.restrict_zone', 'company_id.restrict_product_brand')
    def _compute_show_restriction_fields(self):
        for partner in self:
            company = partner.company_id or self.env.company
            partner.show_customer_class = company.restrict_customer_class
            partner.show_zone = company.restrict_zone
            partner.show_brand = company.restrict_product_brand

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
        if self.env.context.get('custom_customer_action'):
            custom_domain = self._get_partner_domain()
            if custom_domain:
                domain = expression.AND([domain, custom_domain]) if domain else custom_domain
        return super(ResPartner, self).web_search_read(domain, *args, **kwargs)

    @api.depends('name', 'street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def _compute_display_name(self):
        show_address = self.env.context.get('show_customer_address', False)
        for partner in self:
            try:
                partner.check_access_rights('read')
                partner.check_access_rule('read')
                name = partner.name or ''
                if show_address:
                    address_parts = []
                    if partner.street:
                        address_parts.append(partner.street)
                    if partner.street2:
                        address_parts.append(partner.street2)
                    if partner.city:
                        address_parts.append(partner.city)
                    if partner.state_id:
                        address_parts.append(partner.state_id.name)
                    if partner.zip:
                        address_parts.append(partner.zip)
                    if address_parts:
                        address = ', '.join(address_parts)
                        partner.display_name = f"{name} - {address}"
                    else:
                        partner.display_name = name
                else:
                    partner.display_name = name
            except (AccessError, MissingError):
                partner.display_name = "Restricted Contact"


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'Product Brand'
    _rec_name = 'name'

    name = fields.Char(string='Brand Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)


class _PartnerDomainMixin(models.AbstractModel):
    _name = 'partner.domain.mixin'
    _description = 'Partner Domain Mixin'

    @api.model
    def _get_partner_domain(self):
        employee = self.env.user.employee_id
        domain = []
        if not employee:
            return domain

        # Get the current company from context or user
        current_company = self.env.company

        if employee.customer_access_scope == 'all':
            domain = [
                ('parent_id', '=', False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                # ('employee_ids', '=', False),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]

        elif employee.customer_access_scope == 'self':
            domain = [
                ('customer_visibility_access', '=', employee.id),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_type', '!=', 'distribution'),
                ('company_id', 'in', [False, current_company.id]),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'assigned':
            assignment_lines = self.env['customer.assignment.line'].search([
                ('assignee_name', '=', employee.id),
                ('company_id', '=', current_company.id)
            ])
            assigned_customers = assignment_lines.mapped('client_id')
            domain = [
                ('id', 'in', assigned_customers.ids),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'select':
            select_domain = []
            # Use the employee's company or current company
            company = employee.company_id or current_company

            if employee.restrict_by_location:
                # ZONE/SUB-ZONE FILTERING - SIMPLIFIED
                if company.restrict_zone and employee.location_restriction_zone:
                    zone_filter_ids = []

                    # FIRST: Check if sub-zones are selected
                    if employee.allowed_sub_zone_ids:
                        zone_filter_ids = employee.allowed_sub_zone_ids.ids
                    # SECOND: If no sub-zones selected, check main zones
                    elif employee.allowed_zone_ids:
                        # Get all sub-zones under the selected main zones
                        sub_zones_from_zones = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ])
                        zone_filter_ids = sub_zones_from_zones.ids

                    # Apply the filter if we have any zone IDs
                    if zone_filter_ids:
                        select_domain.append(('zone_id', 'in', zone_filter_ids))
                if company.restrict_state and employee.location_restriction_state and employee.allowed_state_ids:
                    select_domain.append(('state_id', 'in', employee.allowed_state_ids.ids))
                if company.restrict_city and employee.location_restriction_city and employee.allowed_city_ids:
                    if 'city_id' in self.env['res.partner']._fields:
                        select_domain.append(('city_id', 'in', employee.allowed_city_ids.ids))
                    else:
                        select_domain.append(('city', 'in', employee.allowed_city_ids.mapped('name')))

            if employee.restrict_by:
                if company.restrict_customer_class and employee.customer_class and employee.allowed_customer_class_ids:
                    select_domain.append(('customer_class_id', 'in', employee.allowed_customer_class_ids.ids))
                if company.restrict_product_brand and employee.product_brand and employee.allowed_product_brand_ids:
                    select_domain.append(('brand_id', 'in', employee.allowed_product_brand_ids.ids))

            # Final domain with company restriction
            if select_domain:
                select_domain.append(('parent_id', '=', False))
                select_domain.append(('company_id', 'in', [False, current_company.id]))
                domain = select_domain
            elif employee.allowed_customer_ids:
                domain = [
                    ('id', 'in', employee.allowed_customer_ids.ids),
                    ('parent_id', '=', False),
                    # ("employee_ids", "=", False),
                    ('company_id', 'in', [False, current_company.id]),
                    ('company_type', '!=', 'distribution'),
                    '|',
                    ('user_ids', '=', False),
                    ('user_ids.share', '=', True),
                ]
            else:
                domain = [('id', '=', False)]  # No access if no restrictions defined

        # Add company filter to ensure multi-company safety
        if not any(term[0] == 'company_id' for term in domain):
            domain.append(('company_id', 'in', [False, current_company.id]))

        # Simple exclusion: hide contacts linked to employees without users
        domain.append(('id', 'not in', self.env['hr.employee'].sudo().search([
            ('user_id', '=', False),
            ('company_id', 'in', [False, current_company.id])
        ]).mapped('work_contact_id').ids))

        return domain


class ProjectTask(models.Model):
    _inherit = ['project.task', 'partner.domain.mixin']
    _name = 'project.task'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain(),
                                 context={'show_customer_address': True})


class ProjectProject(models.Model):
    _inherit = ['project.project', 'partner.domain.mixin']
    _name = 'project.project'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain(),
                                 context={'show_customer_address': True})


class AmcContract(models.Model):
    _inherit = ['amc.contract', 'partner.domain.mixin']
    _name = 'amc.contract'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain(),
                                 context={'show_customer_address': True})


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'partner.domain.mixin']
    _name = 'sale.order'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain(),
                                 context={'show_customer_address': True})


class CrmLead2OpportunityPartner(models.TransientModel):
    _inherit = ['crm.lead2opportunity.partner', 'partner.domain.mixin']
    _name = 'crm.lead2opportunity.partner'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain(),
                                 context={'show_customer_address': True})


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain())

    @api.model
    def _get_partner_domain(self):
        employee = self.env.user.employee_id
        domain = []
        if not employee:
            return domain

        # Get the current company from context or user
        current_company = self.env.company

        if employee.customer_access_scope == 'all':
            domain = [
                ('parent_id', '=', False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                # ('employee_ids', '=', False),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]

        elif employee.customer_access_scope == 'self':
            domain = [
                ('customer_visibility_access', '=', employee.id),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_type', '!=', 'distribution'),
                ('company_id', 'in', [False, current_company.id]),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'assigned':
            assignment_lines = self.env['customer.assignment.line'].search([
                ('assignee_name', '=', employee.id),
                ('company_id', '=', current_company.id)
            ])
            assigned_customers = assignment_lines.mapped('client_id')
            domain = [
                ('id', 'in', assigned_customers.ids),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'select':
            select_domain = []
            # Use the employee's company or current company
            company = employee.company_id or current_company

            if employee.restrict_by_location:
                # ZONE/SUB-ZONE FILTERING - SIMPLIFIED
                if company.restrict_zone and employee.location_restriction_zone:
                    zone_filter_ids = []

                    # FIRST: Check if sub-zones are selected
                    if employee.allowed_sub_zone_ids:
                        zone_filter_ids = employee.allowed_sub_zone_ids.ids
                    # SECOND: If no sub-zones selected, check main zones
                    elif employee.allowed_zone_ids:
                        # Get all sub-zones under the selected main zones
                        sub_zones_from_zones = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ])
                        zone_filter_ids = sub_zones_from_zones.ids

                    # Apply the filter if we have any zone IDs
                    if zone_filter_ids:
                        select_domain.append(('zone_id', 'in', zone_filter_ids))
                if company.restrict_state and employee.location_restriction_state and employee.allowed_state_ids:
                    select_domain.append(('state_id', 'in', employee.allowed_state_ids.ids))
                if company.restrict_city and employee.location_restriction_city and employee.allowed_city_ids:
                    if 'city_id' in self.env['res.partner']._fields:
                        select_domain.append(('city_id', 'in', employee.allowed_city_ids.ids))
                    else:
                        select_domain.append(('city', 'in', employee.allowed_city_ids.mapped('name')))

            if employee.restrict_by:
                if company.restrict_customer_class and employee.customer_class and employee.allowed_customer_class_ids:
                    select_domain.append(('customer_class_id', 'in', employee.allowed_customer_class_ids.ids))
                if company.restrict_product_brand and employee.product_brand and employee.allowed_product_brand_ids:
                    select_domain.append(('brand_id', 'in', employee.allowed_product_brand_ids.ids))

            # Final domain with company restriction
            if select_domain:
                select_domain.append(('parent_id', '=', False))
                select_domain.append(('company_id', 'in', [False, current_company.id]))
                domain = select_domain
            elif employee.allowed_customer_ids:
                domain = [
                    ('id', 'in', employee.allowed_customer_ids.ids),
                    ('parent_id', '=', False),
                    # ("employee_ids", "=", False),
                    ('company_id', 'in', [False, current_company.id]),
                    ('company_type', '!=', 'distribution'),
                    '|',
                    ('user_ids', '=', False),
                    ('user_ids.share', '=', True),
                ]
            else:
                domain = [('id', '=', False)]  # No access if no restrictions defined

        # Add company filter to ensure multi-company safety
        if not any(term[0] == 'company_id' for term in domain):
            domain.append(('company_id', 'in', [False, current_company.id]))

        # Simple exclusion: hide contacts linked to employees without users
        domain.append(('id', 'not in', self.env['hr.employee'].sudo().search([
            ('user_id', '=', False),
            ('company_id', 'in', [False, current_company.id])
        ]).mapped('work_contact_id').ids))

        return domain


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    partner_id = fields.Many2one('res.partner', string="Customer", domain=lambda self: self._get_partner_domain())

    @api.model
    def _get_partner_domain(self):
        employee = self.env.user.employee_id
        domain = []
        if not employee:
            return domain

        # Get the current company from context or user
        current_company = self.env.company

        if employee.customer_access_scope == 'all':
            domain = [
                ('parent_id', '=', False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                # ('employee_ids', '=', False),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]

        elif employee.customer_access_scope == 'self':
            domain = [
                ('customer_visibility_access', '=', employee.id),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_type', '!=', 'distribution'),
                ('company_id', 'in', [False, current_company.id]),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'assigned':
            assignment_lines = self.env['customer.assignment.line'].search([
                ('assignee_name', '=', employee.id),
                ('company_id', '=', current_company.id)
            ])
            assigned_customers = assignment_lines.mapped('client_id')
            domain = [
                ('id', 'in', assigned_customers.ids),
                ('parent_id', '=', False),
                # ("employee_ids", "=", False),
                ('company_id', 'in', [False, current_company.id]),
                ('company_type', '!=', 'distribution'),
                '|',
                ('user_ids', '=', False),
                ('user_ids.share', '=', True),
            ]
        elif employee.customer_access_scope == 'select':
            select_domain = []
            # Use the employee's company or current company
            company = employee.company_id or current_company

            if employee.restrict_by_location:
                # ZONE/SUB-ZONE FILTERING - SIMPLIFIED
                if company.restrict_zone and employee.location_restriction_zone:
                    zone_filter_ids = []

                    # FIRST: Check if sub-zones are selected
                    if employee.allowed_sub_zone_ids:
                        zone_filter_ids = employee.allowed_sub_zone_ids.ids
                    # SECOND: If no sub-zones selected, check main zones
                    elif employee.allowed_zone_ids:
                        # Get all sub-zones under the selected main zones
                        sub_zones_from_zones = self.env['sub.zone'].search([
                            ('zone_master_id', 'in', employee.allowed_zone_ids.ids)
                        ])
                        zone_filter_ids = sub_zones_from_zones.ids

                    # Apply the filter if we have any zone IDs
                    if zone_filter_ids:
                        select_domain.append(('zone_id', 'in', zone_filter_ids))
                if company.restrict_state and employee.location_restriction_state and employee.allowed_state_ids:
                    select_domain.append(('state_id', 'in', employee.allowed_state_ids.ids))
                if company.restrict_city and employee.location_restriction_city and employee.allowed_city_ids:
                    if 'city_id' in self.env['res.partner']._fields:
                        select_domain.append(('city_id', 'in', employee.allowed_city_ids.ids))
                    else:
                        select_domain.append(('city', 'in', employee.allowed_city_ids.mapped('name')))

            if employee.restrict_by:
                if company.restrict_customer_class and employee.customer_class and employee.allowed_customer_class_ids:
                    select_domain.append(('customer_class_id', 'in', employee.allowed_customer_class_ids.ids))
                if company.restrict_product_brand and employee.product_brand and employee.allowed_product_brand_ids:
                    select_domain.append(('brand_id', 'in', employee.allowed_product_brand_ids.ids))

            # Final domain with company restriction
            if select_domain:
                select_domain.append(('parent_id', '=', False))
                select_domain.append(('company_id', 'in', [False, current_company.id]))
                domain = select_domain
            elif employee.allowed_customer_ids:
                domain = [
                    ('id', 'in', employee.allowed_customer_ids.ids),
                    ('parent_id', '=', False),
                    # ("employee_ids", "=", False),
                    ('company_id', 'in', [False, current_company.id]),
                    ('company_type', '!=', 'distribution'),
                    '|',
                    ('user_ids', '=', False),
                    ('user_ids.share', '=', True),
                ]
            else:
                domain = [('id', '=', False)]  # No access if no restrictions defined

        # Add company filter to ensure multi-company safety
        if not any(term[0] == 'company_id' for term in domain):
            domain.append(('company_id', 'in', [False, current_company.id]))

        # Simple exclusion: hide contacts linked to employees without users
        domain.append(('id', 'not in', self.env['hr.employee'].sudo().search([
            ('user_id', '=', False),
            ('company_id', 'in', [False, current_company.id])
        ]).mapped('work_contact_id').ids))

        return domain
