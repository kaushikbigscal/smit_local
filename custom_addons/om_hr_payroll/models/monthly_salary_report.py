from lxml import etree
from odoo import models, fields, api, tools

import logging

_logger = logging.getLogger(__name__)


class MonthlySalaryReport(models.Model):
    _name = 'monthly.salary.report'
    _description = 'Monthly Salary Report'
    _auto = False
    _rec_name = 'employee_id'

    # Basic static fields
    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_code = fields.Char(string='Employee Code')
    employee_name = fields.Char(string='Employee Name')
    month = fields.Char(string='Month')
    company_id = fields.Many2one('res.company', string='Company Name')
    department_id = fields.Many2one('hr.department', string='Department Name')
    date_from = fields.Date(string='Start Date')

    def _get_used_salary_rules(self):
        """Get only salary rules that are used in salary structures, ordered by sequence"""
        try:
            # Get all salary structures (remove active filter as it doesn't exist)
            structures = self.env['hr.payroll.structure'].search([])
            if not structures:
                _logger.warning("No salary structures found")
                return self.env['hr.salary.rule'].browse([])

            _logger.info(f"Found {len(structures)} salary structures")

            # Debug: Check what fields are available in salary structure
            structure_fields = structures[0]._fields
            rule_related_fields = [f for f in structure_fields.keys() if 'rule' in f.lower()]
            _logger.info(f"Rule-related fields in hr.payroll.structure: {rule_related_fields}")

            # Get all rule IDs from all structures
            rule_ids = []
            for structure in structures:
                _logger.info(f"Processing structure: {structure.name}")

                # Try different possible field names
                possible_fields = ['rule_ids', 'salary_rule_ids', 'hr_salary_rule_ids', 'payslip_rule_ids']
                found_rules = False

                for field_name in possible_fields:
                    if hasattr(structure, field_name):
                        field_value = getattr(structure, field_name)
                        if field_value:
                            rule_ids.extend(field_value.ids)
                            _logger.info(f"Structure '{structure.name}' -> {field_name}: {field_value.mapped('code')}")
                            found_rules = True
                            break

                if not found_rules:
                    _logger.warning(f"No salary rules found in structure '{structure.name}' using any known field")
                    # Debug: Show all fields that contain 'rule' or are Many2many/One2many
                    debug_fields = []
                    for fname, field in structure._fields.items():
                        if ('rule' in fname.lower() or
                                field.type in ['many2many', 'one2many']):
                            debug_fields.append(f"{fname} ({field.type})")
                    _logger.info(f"Available Many2many/One2many and rule fields in '{structure.name}': {debug_fields}")

            # Remove duplicates
            rule_ids = list(set(rule_ids))

            if not rule_ids:
                _logger.warning("No salary rules found in any salary structures")
                # Let's try a fallback approach - get rules that have been used in payslips
                _logger.info("Trying fallback: getting rules from recent payslips")
                recent_payslip_rules = self.env['hr.payslip.line'].search([
                    ('slip_id.state', '=', 'done')
                ], limit=100).mapped('salary_rule_id')

                if recent_payslip_rules:
                    rule_ids = recent_payslip_rules.ids
                    _logger.info(
                        f"Fallback found {len(recent_payslip_rules)} rules from payslips: {recent_payslip_rules.mapped('code')}")
                else:
                    # Final fallback - just get all salary rules for now to test
                    _logger.info("No rules found anywhere, using all salary rules as final fallback")
                    all_rules = self.env['hr.salary.rule'].search([])
                    return all_rules.sorted(lambda r: (r.sequence, r.name))

            # Get only the rules that are used, ordered by sequence
            used_rules = self.env['hr.salary.rule'].browse(rule_ids).sorted(lambda r: (r.sequence, r.name))
            _logger.info(f"Final result: {len(used_rules)} salary rules to be used: {used_rules.mapped('code')}")

            return used_rules

        except Exception as e:
            _logger.error(f"Error getting used salary rules: {str(e)}")
            import traceback
            _logger.error(f"Full traceback: {traceback.format_exc()}")
            # Return all rules as fallback to ensure columns are generated
            _logger.info("Error occurred, using all salary rules as fallback")
            return self.env['hr.salary.rule'].search([]).sorted(lambda r: (r.sequence, r.name))

    def _register_dynamic_fields(self):
        """Register dynamic fields for salary rules used in salary structures only"""
        # Clear any existing dynamic fields first
        for field_name in list(self._fields.keys()):
            if field_name.startswith('x_'):
                self._pop_field(field_name)

        # Register new fields only for used rules
        field_count = 0
        used_rules = self._get_used_salary_rules()

        if not used_rules:
            _logger.warning("No salary rules found in salary structures - no dynamic fields will be created")
            return False

        for rule in used_rules:
            # Sanitize the code to create a valid field name
            sanitized_code = ''.join(
                c if c.isalnum() else '_'
                for c in rule.code.lower()
            )
            # Remove consecutive underscores and trailing underscores
            sanitized_code = '_'.join(filter(None, sanitized_code.split('_')))
            field_name = f"x_{sanitized_code}"

            if not hasattr(self.__class__, field_name):
                field = fields.Float(
                    string=rule.name,
                    readonly=True,
                    default=0.0,
                    digits=(16, 2)
                )
                self._add_field(field_name, field)
                field_count += 1
                _logger.info(f"Registered field {field_name} for rule {rule.code} ({rule.name})")

        return field_count > 0

    def _register_hook(self):
        """Register dynamic fields when model is loaded"""
        super()._register_hook()

        # Debug: Check what fields exist in hr.payroll.structure
        structure_model = self.env['hr.payroll.structure']
        structure_fields = structure_model._fields.keys()
        _logger.info(
            f"Available fields in hr.payroll.structure: {[f for f in structure_fields if 'rule' in f.lower()]}")

        # Verification 1: Log used salary rules only
        used_rules = self._get_used_salary_rules()
        _logger.info(f"Found {len(used_rules)} salary rules used in structures to register as fields")
        # for rule in used_rules:
        #     _logger.info(f"Used Rule: {rule.code} ({rule.name}) - Sequence: {rule.sequence}")

        self._register_dynamic_fields()

        # Verification 2: Check registered fields
        field_count = len([f for f in self._fields if f.startswith('x_')])
        _logger.info(f"Registered {field_count} dynamic salary rule fields for used rules only")

        self._create_dynamic_view()

    def _create_dynamic_view(self):
        """Create SQL view with all current fields, for all employees with payslips from all months"""
        try:
            tools.drop_view_if_exists(self.env.cr, self._table)

            # Start building query - NO hardcoded month filter
            select_parts = [
                f"""CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT 
                        row_number() OVER () AS id,
                        e.id AS employee_id,
                        e."x_empCode" AS employee_code,
                        e.name AS employee_name,
                        TO_CHAR(p.date_from, 'Mon-YY') AS month,
                        p.date_from AS date_from,
                        e.company_id AS company_id,
                        e.department_id AS department_id,"""
            ]

            # Add dynamic fields for salary rules (only used ones)
            dynamic_fields = [f for f in self._fields.items() if f[0].startswith('x_')]
            used_rules = self._get_used_salary_rules()

            for field_name, field in dynamic_fields:
                # Get the original rule code by removing 'x_' prefix
                sanitized_code = field_name[2:]
                # Find all used rules that would generate this sanitized code
                rule_codes = []
                for rule in used_rules:
                    rule_sanitized = ''.join(
                        c if c.isalnum() else '_'
                        for c in rule.code.lower()
                    )
                    rule_sanitized = '_'.join(filter(None, rule_sanitized.split('_')))
                    if rule_sanitized == sanitized_code:
                        rule_codes.append(rule.code)

                if not rule_codes:
                    continue

                # Modified: Remove hardcoded month filter, match payslip dates instead
                select_parts.append(f"""
                    COALESCE((
                        SELECT SUM(pl.amount) 
                        FROM hr_payslip_line pl
                        JOIN hr_payslip p2 ON pl.slip_id = p2.id
                        WHERE p2.employee_id = e.id
                        AND pl.salary_rule_id IN (
                            SELECT id FROM hr_salary_rule 
                            WHERE code IN ({','.join(f"'{code}'" for code in rule_codes)})
                        )
                        AND p2.state = 'done'
                        AND p2.date_from = p.date_from
                        GROUP BY p2.employee_id, p2.date_from
                    ), 0) AS {field_name},""")

            # Remove trailing comma
            if select_parts[-1].endswith(','):
                select_parts[-1] = select_parts[-1][:-1]

            # Complete query - Show ALL months, not just current month
            select_parts.append(f"""
                FROM hr_employee e
                JOIN hr_payslip p ON p.employee_id = e.id
                WHERE e.active = true
                AND p.state = 'done'
                GROUP BY e.id, e."x_empCode", e.name, p.date_from, e.company_id, e.department_id
            )""")

            # Execute query
            final_sql = '\n'.join(select_parts)
            self.env.cr.execute(final_sql)

            # Verify view contains expected columns
            self.env.cr.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{self._table}'
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in self.env.cr.fetchall()]

            expected_columns = ['id', 'employee_id', 'employee_code', 'employee_name',
                                'month', 'date_from', 'company_id', 'department_id'] + \
                               [f for f in self._fields if f.startswith('x_')]

            if not all(col in columns for col in expected_columns):
                missing = set(expected_columns) - set(columns)
                raise ValueError(f"View missing expected columns: {missing}")

            _logger.info(f"Successfully created view {self._table} with all payslip months")

        except Exception as e:
            _logger.error(f"Failed to create view: {str(e)}")
            raise
    def _get_ordered_dynamic_fields(self):
        """Get dynamic fields ordered by salary rule sequence"""
        used_rules = self._get_used_salary_rules()
        ordered_fields = []

        # Create a mapping of sanitized codes to original rules for ordering
        rule_mapping = {}
        for rule in used_rules:
            sanitized_code = ''.join(
                c if c.isalnum() else '_'
                for c in rule.code.lower()
            )
            sanitized_code = '_'.join(filter(None, sanitized_code.split('_')))
            field_name = f"x_{sanitized_code}"
            rule_mapping[field_name] = rule

        # Get all dynamic fields and order them by rule sequence
        dynamic_fields = [(name, field) for name, field in self._fields.items()
                          if name.startswith('x_')]

        # Sort by rule sequence, then by rule name
        def get_sort_key(field_tuple):
            field_name, field = field_tuple
            if field_name in rule_mapping:
                rule = rule_mapping[field_name]
                return (rule.sequence, rule.name)
            else:
                # Fallback for fields without mapping
                return (9999, field.string)

        ordered_fields = sorted(dynamic_fields, key=get_sort_key)
        return ordered_fields

    def get_dynamic_view(self):
        """Generate complete tree view XML on-the-fly"""
        view_xml = """
        <tree string="Monthly Salary Report" create="false" edit="false">
            <field name="employee_code"/>
            <field name="employee_name"/>
            <field name="month"/>
            <field name="department_id"/>
            <field name="company_id"/>
        """

        # Add all dynamic fields sorted by salary rule sequence (only used rules)
        dynamic_fields = self._get_ordered_dynamic_fields()

        for field_name, field in dynamic_fields:
            view_xml += f'\n<field name="{field_name}" string="{field.string}"/>'

        view_xml += "\n</tree>"
        return view_xml

    def get_dynamic_view_arch(self):
        """Generate complete tree view XML with all fields (only used salary rules)"""
        # Static fields first - these will always be visible
        arch = """
        <tree string="Monthly Salary Report" create="false" edit="false">
            <field name="employee_code"/>
            <field name="employee_name"/>
            <field name="month"/>
            <field name="department_id"/>
            <field name="company_id"/>
        """

        # Add all dynamic fields (only for used salary rules, ordered by sequence)
        dynamic_fields = self._get_ordered_dynamic_fields()

        for field_name, field in dynamic_fields:
            arch += f'\n<field name="{field_name}" string="{field.string}"/>'

        arch += "\n</tree>"
        return arch

    @api.model
    def get_view(self, view_id=None, view_type='tree', **options):
        """Override get_view to use our complete dynamic arch"""
        res = super().get_view(view_id, view_type, **options)

        if view_type == 'tree':
            try:
                arch = self.get_dynamic_view_arch()
                doc = etree.fromstring(arch)
                res['arch'] = etree.tostring(doc, encoding='unicode')
            except Exception as e:
                _logger.error(f"Failed to generate dynamic view: {str(e)}")
                raise

        return res

    @api.model
    def refresh_view(self):
        """Manual method to refresh the view and fields"""
        self._register_hook()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def write(self, vals):
        """Clear caches and refresh report when salary rules change"""
        res = super().write(vals)
        if 'code' in vals or 'name' in vals:
            self.env['monthly.salary.report'].refresh_view()
        return res


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    def write(self, vals):
        """Refresh report when payroll structure rules change"""
        res = super().write(vals)
        if 'rule_ids' in vals:
            self.env['monthly.salary.report'].refresh_view()
        return res


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS hr_payslip_date_state_idx 
            ON hr_payslip (date_from, state)
        """)
        return res