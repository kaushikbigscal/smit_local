# Customer Visibility System - Usage Guide

## Overview

This system provides comprehensive customer visibility control across all `partner_id` fields in Odoo based on employee access scopes. It ensures that dropdown searches, list views, and all partner-related operations respect the configured visibility rules.

## How It Works

### 1. Employee Access Scopes

The system supports four access scopes for employees:

- **'all'**: Shows all customers where `parent_id == False` (only parent companies, not child contacts)
- **'self'**: Shows only customers where `customer_visibility_access == current_employee.id`
- **'select'**: Shows customers from `allowed_customer_ids` field
- **'assigned'**: Applies location and business restrictions based on employee settings

### 2. Automatic Filtering

The system automatically applies visibility filters through:

- **`_name_search`**: Controls dropdown search results
- **`_search`**: Controls all search operations
- **`search_read`**: Controls search and read operations
- **`name_get`**: Controls display names

### 3. Location and Business Restrictions

For employees with 'assigned' scope, the system supports:

- **Location Restrictions**: Zone, State, City
- **Business Restrictions**: Customer Class, Product Brand

## Implementation

### 1. For Existing Models

To add customer visibility to an existing model with `partner_id` fields:

```python
from odoo import models, fields, api

class YourModel(models.Model):
    _inherit = 'your.model'
    _mixin = 'customer.visibility.mixin'

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """Override _search to apply customer visibility filters"""
        domain = self._apply_partner_visibility_to_domain(domain, 'partner_id')
        return super(YourModel, self)._search(domain, offset, limit, order, count, access_rights_uid)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to apply customer visibility filters"""
        domain = self._apply_partner_visibility_to_domain(domain, 'partner_id')
        return super(YourModel, self).search_read(domain, fields, offset, limit, order)

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        """Override _name_search to apply customer visibility filters"""
        domain = self._apply_partner_visibility_to_domain(domain, 'partner_id')
        return super(YourModel, self)._name_search(name, domain, operator, limit, order)
```

### 2. For New Models

To create a new model with customer visibility:

```python
from odoo import models, fields, api

class NewModel(models.Model):
    _name = 'new.model'
    _mixin = 'customer.visibility.mixin'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain=lambda self: self.env['res.partner']._get_partner_search_domain()
    )
```

### 3. In Views

To apply customer visibility in views:

```xml
<field name="partner_id" 
       domain="[('parent_id', '=', False)]"
       context="{'search_default_customer': 1}"/>
```

The domain will be automatically enhanced with visibility rules.

## Usage Examples

### 1. Getting Current Visibility Domain

```python
# Get the current user's customer visibility domain
domain = self.env['res.partner']._get_partner_search_domain()

# Use in field definitions
partner_domain = self.env['res.partner']._get_partner_search_domain()
```

### 2. Applying Visibility to Custom Domains

```python
# Start with a custom domain
custom_domain = [('is_company', '=', True)]

# Apply customer visibility rules
final_domain = self._apply_partner_visibility_to_domain(custom_domain, 'partner_id')
```

### 3. Filtering Partner Recordsets

```python
# Get all partners
all_partners = self.env['res.partner'].search([])

# Filter by visibility rules
visible_partners = self._filter_partners_by_visibility(all_partners)
```

## Configuration

### 1. Company Settings

Enable restriction flags in company settings:

- `restrict_zone`: Enable zone-based restrictions
- `restrict_state`: Enable state-based restrictions
- `restrict_city`: Enable city-based restrictions
- `restrict_customer_class`: Enable customer class restrictions
- `restrict_product_brand`: Enable product brand restrictions

### 2. Employee Settings

Configure each employee's access scope:

- Set `customer_access_scope` to desired value
- Configure location restrictions if using 'assigned' scope
- Configure business restrictions if using 'assigned' scope
- Select allowed customers if using 'select' scope

### 3. Customer Assignment

Use the customer assignment system to:

- Assign customers to employees
- Track customer-employee relationships
- Manage visibility access

## Testing

### 1. Demo Model

Use the included demo model to test visibility:

1. Go to Customer Management > Customer Visibility Demo
2. Try to select customers in the partner fields
3. Notice that only visible customers appear in dropdowns

### 2. Different Scopes

Test with different employee access scopes:

1. **All scope**: Should show all parent customers
2. **Self scope**: Should show only assigned customers
3. **Select scope**: Should show only selected customers
4. **Assigned scope**: Should show customers based on restrictions

## Troubleshooting

### 1. Customers Not Visible

- Check employee's `customer_access_scope` setting
- Verify customer has correct `customer_visibility_access` value
- Check location and business restrictions
- Ensure customer is not a child contact (`parent_id` should be False)

### 2. Performance Issues

- The system uses efficient database queries
- Consider adding database indexes on frequently filtered fields
- Monitor query performance in development

### 3. Domain Issues

- Verify domain syntax in field definitions
- Check that restriction fields exist on customer records
- Ensure proper field relationships

## Best Practices

1. **Always use the mixin** for models with partner fields
2. **Override search methods** to ensure visibility compliance
3. **Test with different user roles** to verify restrictions
4. **Use the demo model** to validate functionality
5. **Monitor performance** in production environments

## Extending the System

### 1. Adding New Restrictions

To add new restriction types:

1. Add fields to the `hr.employee` model
2. Update the visibility logic in `_get_partner_search_domain`
3. Add corresponding fields to `res.partner`
4. Update company settings to enable/disable

### 2. Custom Visibility Rules

To implement custom visibility logic:

1. Override the visibility methods in your models
2. Add custom domain logic
3. Ensure compatibility with existing restrictions

### 3. Integration with Other Modules

The system is designed to work with:

- Sales (sale.order)
- Accounting (account.move)
- Projects (project.project, project.task)
- Any custom models with partner fields

## Support

For issues or questions:

1. Check the demo model functionality
2. Verify employee and customer configurations
3. Review domain syntax and field relationships
4. Test with different access scopes
5. Check company restriction settings
