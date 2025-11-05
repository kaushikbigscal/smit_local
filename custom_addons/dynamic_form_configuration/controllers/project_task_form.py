from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import ast


class TaskForm(http.Controller):

    @http.route('/web/task_form', type='json', auth='user')
    def get_task_form(self):
        return self._get_task_mobile_form_view('project.task', 'project.view_task_form2')

    def _get_task_mobile_form_view(self, model_name, view_xml_id):
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
                    'caching_refresh_time': mf.caching_refresh_time,
                    'is_instant': mf.is_instant,
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

            # Step 3: Dynamically detect FSM-only fields
            fsm_only_fields = [
                field.get('name')
                for field in sheet_fields
                if field.get('name') and 'not is_fsm' in (field.get('invisible') or '')
                # if field.get('invisible') == 'not is_fsm' and field.get('name')
            ]
            print(fsm_only_fields)
            is_fsm = request.env.context.get('is_fsm', False)
            print(is_fsm)

            for field in sheet_fields:
                field_name = field.get('name')
                if not field_name:
                    continue

                if not is_fsm and field_name in fsm_only_fields:
                    continue

                if field_name in mobile_field_map:
                    ordered_fields[field_name] = field

            # Special handling after loop
            if 'tag_ids' in fsm_only_fields:
                ordered_fields['tag_ids'] = next((f for f in sheet_fields if f.get('name') == 'tag_ids'), {})

            if 'partner_id' in fsm_only_fields:
                ordered_fields['partner_id'] = next((f for f in sheet_fields if f.get('name') == 'partner_id'), {})

            if 'date_deadline' in fsm_only_fields:
                ordered_fields['date_deadline'] = next((f for f in sheet_fields if f.get('name') == 'date_deadline'),
                                                       {})

            # Step 4: Get field metadata
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
                        'is_instant': mobile_config.get('is_instant', False),
                        'widget': field_element.get('widget', ''),
                    })

            # Step 5: Add dynamic fields
            # Extract all <field> tags from the XML and map dynamic field names to invisible flags
            sheet_dynamic_fields = {
                field.get('name'): field.get('invisible')
                for field in sheet_fields
                if field.get('name')
            }

            dynamic_fields = request.env['dynamic.fields'].search(
                [('model', '=', model_name), ('form_view_id.name', '!=', 'project.task.view.todo.form'),
                 ('status', '=', 'form')])

            for field in dynamic_fields:
                # Skip FSM-only dynamic fields when is_fsm is False
                xml_invisible = sheet_dynamic_fields.get(field.name)

                if not is_fsm and xml_invisible == 'not is_fsm':
                    continue

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
                    "is_instant": field.is_instant,

                })

            return result

        except Exception as e:
            return {'status': False, 'error': str(e)}


class ProjectForm(http.Controller):

    @http.route('/web/project_form', type='json', auth='user')
    def get_project_form(self):
        return self._get_mobile_form_view('project.project', 'project.edit_project')

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
                        'widget': field_element.get('widget', ''),
                    })

            # Step 4: Add dynamic fields
            dynamic_fields = request.env['dynamic.fields'].search([('model', '=', model_name), ('status', '=', 'form')])
            result['dynamic_fields'] = {
                model_name: []
            }
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
