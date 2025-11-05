# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: MOHAMMED DILSHAD TK (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
from xlrd.xlsx import ET

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class DynamicFields(models.Model):
    """Creates dynamic fields model to create and manage new fields"""
    _name = 'dynamic.fields'
    _rec_name = 'field_description'
    _description = 'Custom Dynamic Fields'
    _inherit = 'ir.model.fields'

    @api.model
    def get_possible_field_types(self):
        """Return all available field types other than 'o2m' and
           'reference' fields."""
        field_list = sorted((key, key) for key in fields.MetaField.by_type)
        field_list.remove(('one2many', 'one2many'))
        field_list.remove(('reference', 'reference'))
        field_list.remove(('json', 'json'))
        field_list.remove(('many2one_reference', 'many2one_reference'))
        field_list.remove(('properties', 'properties'))
        field_list.remove(('properties_definition', 'properties_definition'))
        return field_list

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Pass selected model into model field to filter position fields,
            set values to form_view_ids to filter form view ids and pass
            values to tree_view_ids to filter tree view ids"""
        for rec in self:
            rec.model = rec.model_id.model
            rec.write({'form_view_ids': [(6, 0, rec.model_id.view_ids.filtered(
                lambda view: view.type == 'form')
                                          .ids)]})
            rec.write({'tree_view_ids': [(6, 0, self.model_id.view_ids.filtered(
                lambda view: view.type == 'tree')
                                          .ids)]})

    model = fields.Char(string='Model', help="To store selected model name")
    position_field_id = fields.Many2one(comodel_name='ir.model.fields',
                                        string='Field Name',
                                        required=True, ondelete='cascade',
                                        help="Position field for new field"
                                        , domain=lambda
            self: "[('model', '=', model)]")
    position = fields.Selection(selection=[('before', 'Before'),
                                           ('after', 'After')],
                                string='Position',
                                required=True, help="Position of new field")
    model_id = fields.Many2one(comodel_name='ir.model', string='Model',
                               required=True,
                               index=True,
                               help="The model this field belongs to")
    ref_model_id = fields.Many2one(comodel_name='ir.model', string='Relational '
                                                                   'Model',
                                   index=True, help="Relational model"
                                                    " for relational fields")
    selection_field = fields.Char(string="Selection Options",
                                  help="The model this field belongs to")
    field_type = fields.Selection(selection='get_possible_field_types',
                                  string='Field Type', required=True,
                                  help="Data type of new field")
    tree_field_ids = fields.Many2many('ir.model.fields',
                                      'tree_field_ids',
                                      compute='_compute_tree_field_ids')

    ttype = fields.Selection(string="Field Type", related='field_type',
                             help="Field type of field")

    widget_id = fields.Many2one(comodel_name='dynamic.field.widgets',
                                string='Widget', help="Widgets for field",
                                domain=lambda self: "[('data_type', '=', "
                                                    "field_type)]")
    groups = fields.Many2many('res.groups',
                              'dynamic_fields_group_rel',
                              'dynamic_field_id',
                              'dynamic_group_id',
                              help="Groups of field")
    extra_features = fields.Boolean(string="Show Extra Properties",
                                    help="Enable to add extra features")
    status = fields.Selection(selection=[('draft', 'Draft'), ('form',
                                                              'Field Created')],
                              string='Status',
                              index=True, readonly=True, tracking=True,
                              copy=False, default='draft',
                              help='State for record')
    form_view_ids = fields.Many2many(comodel_name='ir.ui.view',
                                     string="Form View IDs",
                                     help="Stores form view ids")
    tree_view_ids = fields.Many2many(comodel_name='ir.ui.view',
                                     relation="rel_tree_view",
                                     string="Tree View IDs",
                                     help="Stores tree view ids")
    form_view_id = fields.Many2one(comodel_name='ir.ui.view',
                                   string="Form View ID",
                                   required=True,
                                   help="Form view id of the model",
                                   domain=lambda self: "[('id', 'in', "
                                                       "form_view_ids)]")
    form_view_inherit_id = fields.Char(string="Form View Inherit Id",
                                       related='form_view_id.xml_id',
                                       help="Form view inherit id(adds"
                                            " by selecting form view id)")
    add_field_in_tree = fields.Boolean(string="Add Field to the Tree View",
                                       help="Enable to add field in tree view")
    tree_view_id = fields.Many2one(comodel_name='ir.ui.view',
                                   string="Tree View ID",
                                   help="Tree view id of the model",
                                   domain=lambda self: "[('id', 'in', "
                                                       "tree_view_ids)]")
    tree_view_inherit_id = fields.Char(string="External Id",
                                       related='tree_view_id.xml_id',
                                       help="Tree view inherit id(adds"
                                            " by selecting tree view id)")
    tree_field_id = fields.Many2one('ir.model.fields',
                                    string='Tree Field',
                                    help='Position for new field',
                                    domain="[('id', 'in', tree_field_ids)]")
    tree_field_position = fields.Selection(selection=[('before', 'Before'),
                                                      ('after', 'After')],
                                           string='Tree Position',
                                           help="Position of new field in "
                                                "tree view")
    is_visible_in_tree_view = fields.Boolean(string='Visible In List View',
                                             help="Enable to make the field "
                                                  "visible in selected list "
                                                  "view of the model")
    created_tree_view_id = fields.Many2one('ir.ui.view',
                                           string='Created Tree view',
                                           help='This is the currently '
                                                'created tree view')
    created_form_view_id = fields.Many2one('ir.ui.view',
                                           string='Created form view',
                                           help='Created form view id for the '
                                                'dynamic field')

    is_instant = fields.Boolean(string="Is Instant")

    invisible_type = fields.Selection([
        ('none', 'None'),
        ('task', 'For Task'),
        ('service_call', 'For Service Call')
    ], string="Invisible", help="Choose type for invisibility condition")

    show_invisible_type = fields.Boolean(string="Show Invisible Type", compute='_compute_show_invisible_type')

    @api.depends('model_id')
    def _compute_show_invisible_type(self):
        for rec in self:
            rec.show_invisible_type = rec.model_id.model == 'project.task'

    invisible_for_crm = fields.Selection([
        ('none', 'None'),
        ('lead', 'For Lead'),
        ('opportunity', 'For Opportunity')
    ], string="Invisible", help="Choose type for invisibility condition")

    show_invisible_for_crm = fields.Boolean(string="Show Invisible for CRM", compute='_compute_show_invisible_for_crm')

    @api.depends('model_id')
    def _compute_show_invisible_for_crm(self):
        for rec in self:
            rec.show_invisible_for_crm = rec.model_id.model == 'crm.lead'

    @api.onchange('model_id')
    def _onchange_model_id_clear_fields(self):
        self.invisible_type = False
        self.invisible_for_crm = False

    @api.depends('tree_view_id')
    def _compute_tree_field_ids(self):
        """Compute function to find the tree view fields of selected tree view
        in field tree_view_id"""
        for rec in self:
            if rec.tree_view_id:
                field_list = []
                if rec.tree_view_id.xml_id:
                    fields = ET.fromstring(self.env.ref(
                        rec.tree_view_id.xml_id).arch).findall(".//field")
                    for field in fields:
                        field_list.append(field.get('name'))
                inherit_id = rec.tree_view_id.inherit_id if rec.tree_view_id.inherit_id else False
                while inherit_id:
                    if inherit_id.xml_id:
                        fields = ET.fromstring(self.env.ref(
                            inherit_id.xml_id).arch).findall(".//field")
                        for field in fields:
                            field_list.append(field.get('name'))
                    inherit_id = inherit_id.inherit_id if inherit_id.inherit_id else False
                self.tree_field_ids = self.env['ir.model.fields'].search(
                    [('model_id', '=', self.model_id.id),
                     ('name', 'in', field_list)])
            else:
                rec.tree_field_ids = False

    @api.onchange('add_field_in_tree')
    def _onchange_add_field_in_tree(self):
        """Function to clear values of tree_view_id and tree_field_id"""
        if not self.add_field_in_tree:
            self.tree_view_id = False
            self.tree_field_id = False

    # def action_create_dynamic_field(self):
    #     """Function to create dynamic field to a particular model, data type, properties, etc."""
    #     self.write({'status': 'form'})
    #
    #     IrModelFields = self.env['ir.model.fields'].sudo()
    #     IrUIView = self.env['ir.ui.view'].sudo()
    #
    #     # Create currency_id field if type is monetary and currency_id doesn't exist
    #     if self.field_type == 'monetary' and not IrModelFields.search([
    #         ('model_id', '=', self.model_id.id),
    #         ('name', '=', 'currency_id')
    #     ]):
    #         IrModelFields.create({
    #             'name': 'x_currency_id',
    #             'field_description': 'Currency',
    #             'model_id': self.model_id.id,
    #             'ttype': 'many2one',
    #             'relation': 'res.currency',
    #             'is_dynamic_field': True
    #         })
    #
    #     # Create the dynamic field itself
    #     IrModelFields.create({
    #         'name': self.name,
    #         'field_description': self.field_description,
    #         'model_id': self.model_id.id,
    #         'ttype': self.field_type,
    #         'relation': self.ref_model_id.model if self.ref_model_id else None,
    #         'required': self.required,
    #         'index': self.index,
    #         'store': self.store,
    #         'help': self.help,
    #         'readonly': self.readonly,
    #         'selection': self.selection_field,
    #         'copied': self.copied,
    #         'is_dynamic_field': True
    #     })
    #
    #     # Build modifiers (invisible condition)
    #     invisible_attr = ''
    #     if self.model_id.model == 'project.task':
    #         if self.invisible_type == 'none':
    #             invisible_attr = ''
    #         elif self.invisible_type == 'task':
    #             invisible_attr = ' invisible="not is_fsm"'
    #         elif self.invisible_type == 'service_call':
    #             invisible_attr = ' invisible="is_fsm"'
    #     elif self.model_id.model == 'crm.lead':
    #         if self.invisible_for_crm == 'lead':
    #             invisible_attr = ' invisible="type == \'lead\'"'
    #         elif self.invisible_for_crm == 'opportunity':
    #             invisible_attr = ' invisible="type == \'opportunity\'"'
    #         elif self.invisible_for_crm == 'none':
    #             invisible_attr = ' invisible="0"'
    #     elif self.invisible_type:
    #         # Generic fallback
    #         invisible_attr = f' invisible="{self.invisible_type}"'
    #
    #     # Prepare optional widget part
    #     widget_attr = f' widget="{self.widget_id.name}"' if self.widget_id else ''
    #
    #     arch_base = _(
    #         '<?xml version="1.0"?>'
    #         '<data>'
    #         '<field name="%(position_field)s" position="%(position)s">'
    #         '<field name="%(field_name)s"%(widget)s%(invisible)s/>'
    #         '</field>'
    #         '</data>'
    #     ) % {
    #                     'position_field': self.position_field_id.name,
    #                     'position': self.position,
    #                     'field_name': self.name,
    #                     'widget': widget_attr,
    #                     'invisible': invisible_attr
    #                 }
    #
    #     inherit_form_view_name = f"{self.form_view_id.name}.inherit.dynamic.custom.{self.field_description}.field"
    #     inherit_id = self.env.ref(self.form_view_id.xml_id)
    #
    #     # Create the inherited view
    #     self.created_form_view_id = IrUIView.create({
    #         'name': inherit_form_view_name,
    #         'type': 'form',
    #         'model': self.model_id.model,
    #         'mode': 'extension',
    #         'inherit_id': inherit_id.id,
    #         'arch_base': arch_base,
    #         'active': True,
    #     })
    #
    #     # Add field to tree view
    #     self.action_create_to_tree_view()
    #
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'reload',
    #     }

    def action_create_dynamic_field(self):
        """Function to create dynamic field to a particular model, data type, properties, etc."""
        _logger.info("➡️ START: action_create_dynamic_field for record %s", self.id)

        self.write({'status': 'form'})
        _logger.info("✅ Status updated to 'form' for %s", self.id)

        IrModelFields = self.env['ir.model.fields'].sudo()
        IrUIView = self.env['ir.ui.view'].sudo()

        # Create currency_id field if needed
        if self.field_type == 'monetary':
            _logger.info("🔍 Checking for currency_id field in model %s", self.model_id.model)
            if not IrModelFields.search([
                ('model_id', '=', self.model_id.id),
                ('name', '=', 'currency_id')
            ]):
                _logger.info("➕ Creating currency_id field for %s", self.model_id.model)
                IrModelFields.create({
                    'name': 'x_currency_id',
                    'field_description': 'Currency',
                    'model_id': self.model_id.id,
                    'ttype': 'many2one',
                    'relation': 'res.currency',
                    'is_dynamic_field': True
                })
                # self.env.cr.commit()
                _logger.info("✅ Currency_id created successfully")

        # Create the dynamic field
        _logger.info("➕ Creating dynamic field %s (%s)", self.name, self.field_type)
        field_record = IrModelFields.create({
            'name': self.name,
            'field_description': self.field_description,
            'model_id': self.model_id.id,
            'ttype': self.field_type,
            'relation': self.ref_model_id.model if self.ref_model_id else None,
            'required': self.required,
            'index': self.index,
            'store': self.store,
            'help': self.help,
            'readonly': self.readonly,
            'selection': self.selection_field,
            'copied': self.copied,
            'is_dynamic_field': True
        })
        # self.env.cr.commit()
        _logger.info("✅ Dynamic field created: %s", field_record)

        # Build modifiers (invisible condition)
        invisible_attr = ''
        if self.model_id.model == 'project.task':
            if self.invisible_type == 'none':
                invisible_attr = ''
            elif self.invisible_type == 'task':
                invisible_attr = ' invisible="not is_fsm"'
            elif self.invisible_type == 'service_call':
                invisible_attr = ' invisible="is_fsm"'
        elif self.model_id.model == 'crm.lead':
            if self.invisible_for_crm == 'lead':
                invisible_attr = ' invisible="type == \'lead\'"'
            elif self.invisible_for_crm == 'opportunity':
                invisible_attr = ' invisible="type == \'opportunity\'"'
            elif self.invisible_for_crm == 'none':
                invisible_attr = ' invisible="0"'
        elif self.invisible_type:
            invisible_attr = f' invisible="{self.invisible_type}"'

        _logger.info("⚙️ Invisible attribute built: %s", invisible_attr)

        widget_attr = f' widget="{self.widget_id.name}"' if self.widget_id else ''
        _logger.info("⚙️ Widget attribute built: %s", widget_attr)

        arch_base = _(
            '<?xml version="1.0"?>'
            '<data>'
            '<field name="%(position_field)s" position="%(position)s">'
            '<field name="%(field_name)s"%(widget)s%(invisible)s/>'
            '</field>'
            '</data>'
        ) % {
                        'position_field': self.position_field_id.name,
                        'position': self.position,
                        'field_name': self.name,
                        'widget': widget_attr,
                        'invisible': invisible_attr
                    }

        _logger.info("📝 arch_base prepared for field %s", self.name)

        inherit_form_view_name = f"{self.form_view_id.name}.inherit.dynamic.custom.{self.field_description}.field"
        inherit_id = self.env.ref(self.form_view_id.xml_id)
        _logger.info("📄 Creating inherited form view: %s", inherit_form_view_name)

        try:
            self.created_form_view_id = IrUIView.create({
                'name': inherit_form_view_name,
                'type': 'form',
                'model': self.model_id.model,
                'mode': 'extension',
                'inherit_id': inherit_id.id,
                'arch_base': arch_base,
                'active': True,
            })
            # self.env.cr.commit()
            _logger.info("✅ Inherited form view created: %s", self.created_form_view_id)

        except Exception as e:
            _logger.error("❌ Failed to create inherited view: %s", str(e), exc_info=True)
            raise

        # Add field to tree view
        _logger.info("➡️ Calling action_create_to_tree_view for %s", self.id)
        self.action_create_to_tree_view()
        _logger.info("✅ action_create_to_tree_view completed")

        _logger.info("🏁 END: action_create_dynamic_field for %s", self.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': self._name,
        #     'view_mode': 'form',
        #     'res_id': self.id,
        #     'target': 'current',
        # }

    def action_create_to_tree_view(self):
        """Function to add field to tree view"""
        if self.add_field_in_tree:
            optional = "show" if self.is_visible_in_tree_view else "hide"
            tree_view_arch_base = (_(f'''
                                    <data>
                                    <xpath expr="//field[@name='{self.tree_field_id.name}']" position="{self.tree_field_position}">
                                    <field name="{self.name}" optional="{optional}"/>
                            </xpath>
                            </data>'''))
            inherit_tree_view_name = str(
                self.tree_view_id.name) + ".inherit.dynamic.custom" + \
                                     str(self.field_description) + ".field"
            self.created_tree_view_id = self.env['ir.ui.view'].sudo().create({
                'name': inherit_tree_view_name,
                'type': 'tree',
                'model': self.model_id.model,
                'mode': 'extension',
                'inherit_id': self.tree_view_id.id,
                'arch_base': tree_view_arch_base,
                'active': True})
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    # def unlink(self):
    #     """Super unlink function"""
    #     if self.form_view_id:
    #         self.created_form_view_id.active = False
    #     if self.tree_view_id:
    #         self.created_tree_view_id.active = False
    #     res = super(DynamicFields, self).unlink()
    #     return res

    def unlink(self):
        """Super unlink function that also deletes the field from ir.model.fields"""
        # Deactivate the created views
        if self.form_view_id:
            self.created_form_view_id.active = False
        if self.tree_view_id:
            self.created_tree_view_id.active = False

        # Check the field type and delete from ir.model.fields only if it's not Many2many
        field = self.env['ir.model.fields'].sudo().search([
            ('name', '=', self.name),
            ('model_id', '=', self.model_id.id),
            ('is_dynamic_field', '=', True)
        ])

        # Only delete the field if its type is not Many2many
        if field and field.ttype != 'many2many':
            field.unlink()

        # Continue with normal deletion of this record
        res = super(DynamicFields, self).unlink()
        return res
