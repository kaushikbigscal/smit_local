from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import ast


class TodoForm(http.Controller):

    @http.route('/web/todo_form', type='json', auth='user')
    def get_todo_form(self):
        return self._get_mobile_form_view('project.task', 'project_todo.project_task_view_todo_form')

    def _get_mobile_form_view(self, model_name, view_xml_id):
        try:
            if not model_name or not view_xml_id:
                return {'status': False, 'error': 'Model and view_xml_id are required'}

            # Step 1: Get mobile-enabled fields with caching info
            mobile_fields = request.env['ir.model.fields.mobile'].search([
                ('model_id.model', '=', model_name),
                ('for_mobile', '=', True)
            ])
            mobile_field_map = {
                mf.field_id.name: {
                    'is_caching': mf.is_caching,
                    'caching_refresh_time': mf.caching_refresh_time
                }
                for mf in mobile_fields if mf.field_id
            }

            if not mobile_field_map:
                return {'status': False, 'error': 'No mobile fields found for this model'}

            # Step 2: Get view architecture
            model = request.env[model_name]
            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': False, 'error': f'View {view_xml_id} not found'}

            view_info = model.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': False, 'error': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)
            # sheet_fields = list(arch_tree.iter("field"))
            form_elements = list(arch_tree.iter("form"))
            if form_elements:
                form_element = form_elements[0]  # Get the first <form> element

                # Get the <sheet> element within the <form>
                sheet_elements = list(form_element.iter("sheet"))
                if sheet_elements:
                    sheet_element = sheet_elements[0]  # Get the first <sheet> element
                    sheet_fields = list(sheet_element.iter("field"))
                else:
                    sheet_fields = []  # No <sheet> found
            else:
                sheet_fields = []  # No <form> found
            ordered_fields = OrderedDict()

            for field in sheet_fields:
                field_name = field.get('name')
                if field_name and field_name in mobile_field_map:
                    ordered_fields[field_name] = field

            # Step 3: Get field metadata
            fields_data = model.fields_get()
            result = {
                'models': {
                    model_name: []
                },
                'dynamic_fields': {
                    model_name: []
                }
            }

            for field_name, field_element in ordered_fields.items():
                if field_name in fields_data:
                    field_info = fields_data[field_name]
                    mobile_config = mobile_field_map[field_name]

                    result['models'][model_name].append({
                        'name': field_name,
                        'string': field_info.get('string', field_name),
                        'type': field_info.get('type', 'char'),
                        'readonly': field_info.get('readonly', False),
                        'required': field_info.get('required', False),
                        'is_caching': mobile_config.get('is_caching', False),
                        'caching_refresh_time': mobile_config.get('caching_refresh_time', ''),
                    })

            # Step 4: Add dynamic fields
            dynamic_fields = request.env['dynamic.fields'].search(
                [('model', '=', model_name), ('form_view_id.name', '=', 'project.task.view.todo.form'),
                 ('status', '=', 'form')])

            for field in dynamic_fields:
                selection_data = []
                if field.selection_field:
                    try:
                        selection_data = ast.literal_eval(field.selection_field)
                    except Exception:
                        selection_data = []
                result['dynamic_fields'][model_name].append({
                    "name": field.name,
                    "field_description": field.field_description,
                    "field_type": field.field_type,
                    "selection_field": selection_data,
                    "ref_model_id": {
                        "fields": {
                            "model": field.ref_model_id.model if field.ref_model_id else False
                        }
                    },
                    "widget_id": {
                        "fields": {
                            "name": field.widget_id.display_name if field.widget_id else False
                        }
                    },
                    "required": field.required,
                    "readonly": field.readonly,
                })

            return result

        except Exception as e:
            return {'status': False, 'error': str(e)}

# from odoo import http
# from odoo.http import request
# from lxml import etree
#
#
# class TodoForm(http.Controller):
#
#     @http.route('/web/todo_form', type='json', auth='user')
#     def get_todo_form(self):
#         """
#         API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
#         Only returns fields that are within form/sheet/field structure.
#         Includes visibility conditions extracted from the view XML.
#         """
#         try:
#             model_name = "project.task"
#             view_xml_id = "project_todo.project_task_view_todo_form"
#
#             if not model_name or not view_xml_id:
#                 return {'status': 'false', 'error': 'Model and view_xml_id are required'}
#
#             model = request.env[model_name]
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': 'false', 'error': f'View {view_xml_id} not found'}
#
#             view_info = model.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': 'false', 'error': 'View architecture not found'}
#
#             arch_tree = etree.fromstring(arch)
#             sheet_fields = arch_tree.xpath("//form//sheet//field")
#             sheet_field_names = [field.get('name') for field in sheet_fields if field.get('name')]
#
#             fields_data = model.fields_get()
#
#             # Fetch 'for_mobile' fields with caching attributes
#             mobile_fields = request.env['ir.model.fields.mobile'].search([
#                 ('model_id.model', '=', model_name),
#                 ('for_mobile', '=', True)
#             ])
#             mobile_field_data = {
#                 field.field_id.name: {
#                     "is_caching": field.is_caching if hasattr(field, 'is_caching') else False,
#                     "caching_refresh_time": field.caching_refresh_time if hasattr(field,
#                                                                                   'caching_refresh_time') else False
#                 }
#                 for field in mobile_fields if field.field_id
#             }
#
#             result = {'models': {model_name: []}}
#             field_attributes = self._get_view_field()
#
#             for field_name in sheet_field_names:
#                 if field_name in fields_data:
#                     field_info = fields_data.get(field_name, {})
#                     view_field = arch_tree.xpath(f"//form//sheet//field[@name='{field_name}']")
#                     visibility_conditions = {}
#
#                     if view_field:
#                         field_element = view_field[0]
#                         invisible_condition = field_element.get('invisible', False)
#                         widget = field_element.get('widget', False)
#                         visibility_conditions = {
#                             'invisible': invisible_condition,
#                             'widget': widget
#                         }
#
#                     is_caching = mobile_field_data.get(field_name, {}).get('is_caching', False)
#                     caching_refresh_time = mobile_field_data.get(field_name, {}).get('caching_refresh_time', False)
#
#                     result['models'][model_name].append({
#                         **{attr: field_info.get(attr, False) for attr in field_attributes},
#                         **visibility_conditions,
#                         "is_caching": is_caching,
#                         "caching_refresh_time": caching_refresh_time,
#                     })
#
#             return result
#
#         except Exception as e:
#             return {'status': 'false', 'error': str(e)}
#
#     def _get_view_field(self):
#         """ Returns the field attributes required by the web client to load the views.
#         :return: string list of field attribute names
#         :rtype: list
#         """
#         return [
#             'name', 'string', 'type', 'readonly', 'related', 'context', 'groups', 'domain', 'help', 'relation',
#             'relation_field', 'required', 'searchable', 'selection'
#         ]
