from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import ast


class ServiceCallForm(http.Controller):

    @http.route('/web/service_call_form', type='json', auth='user')
    def get_service_call_form(self):
        return self._get_call_mobile_form_view('project.task', 'project.view_task_form2')

    def _get_call_mobile_form_view(self, model_name, view_xml_id):
        try:
            if not model_name or not view_xml_id:
                return {'status': False, 'error': 'Model and view_xml_id are required'}

            # Step 1: Get mobile-enabled fields
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
            form_elements = list(arch_tree.iter("form"))

            if form_elements:
                form_element = form_elements[0]
                sheet_elements = list(form_element.iter("sheet"))
                sheet_fields = list(sheet_elements[0].iter("field")) if sheet_elements else []
            else:
                sheet_fields = []

            ordered_fields = OrderedDict()

            # Step 3: Include all mobile-enabled fields
            fsm_only_fields = [
                field.get('name')
                for field in sheet_fields
                if field.get('invisible') == 'is_fsm' and field.get('name')
            ]
            print(fsm_only_fields)
            # is_fsm = request.env.context.get('is_fsm', False)
            is_fsm = True
            print(is_fsm)

            for field in sheet_fields:
                field_name = field.get('name')
                if not field_name:
                    continue

                if is_fsm and field_name in fsm_only_fields:
                    continue

                if field_name in mobile_field_map:
                    ordered_fields[field_name] = field

            # Special handling after loop
            if 'tag_ids' in fsm_only_fields:
                ordered_fields['tag_ids'] = next((f for f in sheet_fields if f.get('name') == 'tag_ids'), {})
            if 'date_deadline' in fsm_only_fields:
                ordered_fields['date_deadline'] = next((f for f in sheet_fields if f.get('name') == 'date_deadline'),
                                                       {})

            if 'allocated_hours' in ordered_fields:
                ordered_fields.pop('allocated_hours', None)

            # Step 5: Get field metadata
            fields_data = model.fields_get()
            result = {
                'models': {
                    model_name: []
                },
                'dynamic_fields': {
                    model_name: []
                }
            }

            for field_name, field_elem in ordered_fields.items():
                if field_name in fields_data:
                    field_info = fields_data[field_name]
                    mobile_config = mobile_field_map[field_name]

                    # Get the 'required' attribute from XML
                    xml_required_attr = (field_elem.get('required') or '').strip()
                    # Default value
                    xml_required = False

                    # Normalize and evaluate XML required
                    if xml_required_attr.lower() in ['1', 'true']:
                        xml_required = True
                    elif 'is_fsm' in xml_required_attr and is_fsm:
                        xml_required = True

                    result['models'][model_name].append({
                        'name': field_name,
                        'string': field_info.get('string', field_name),
                        'type': field_info.get('type', 'char'),
                        'readonly': field_info.get('readonly', False),
                        'required': xml_required or field_info.get('required', False),
                        'is_caching': mobile_config.get('is_caching', False),
                        'caching_refresh_time': mobile_config.get('caching_refresh_time', ''),
                        'widget': field_elem.get('widget', '')

                    })

            # Step 6: Add dynamic fields — only those meant for FSM
            sheet_dynamic_fields = {
                field.get('name'): field.get('invisible')
                for field in sheet_fields
                if field.get('name')
            }

            dynamic_fields = request.env['dynamic.fields'].search(
                [('model', '=', model_name), ('form_view_id.name', '!=', 'project.task.view.todo.form'),
                 ('status', '=', 'form')])

            for field in dynamic_fields:
                xml_invisible = sheet_dynamic_fields.get(field.name)

                # Skip FSM-only fields if is_fsm is False
                if not is_fsm and xml_invisible == 'is_fsm':
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
                })

            return result

        except Exception as e:
            return {'status': False, 'error': str(e)}


class EndServiceCallForm(http.Controller):

    @http.route('/web/end_service_call_form', type='json', auth='user')
    def get_end_service_call_form(self):
        return self._get_call_mobile_form_view('end.service.call.wizard', 'industry_fsm.view_end_wizard_2')

    def _get_call_mobile_form_view(self, model_name, view_xml_id):
        try:
            if not model_name or not view_xml_id:
                return {'status': False, 'error': 'Model and view_xml_id are required'}

            # Step 1: Get mobile-enabled fields
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
            form_elements = list(arch_tree.iter("form"))

            if form_elements:
                form_element = form_elements[0]
                sheet_elements = list(form_element.iter("sheet"))
                sheet_fields = list(sheet_elements[0].iter("field")) if sheet_elements else []
            else:
                sheet_fields = []

            ordered_fields = OrderedDict()

            # Step 3: Include all mobile-enabled fields
            fsm_only_fields = [
                field.get('name')
                for field in sheet_fields
                if field.get('invisible') == 'is_fsm' and field.get('name')
            ]
            is_fsm = True  # or determine from context

            for field in sheet_fields:
                field_name = field.get('name')
                if not field_name:
                    continue

                if is_fsm and field_name in fsm_only_fields:
                    continue

                if field_name in mobile_field_map:
                    ordered_fields[field_name] = field

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

            for field_name, field_elem in ordered_fields.items():
                if field_name in fields_data:
                    field_info = fields_data[field_name]
                    mobile_config = mobile_field_map[field_name]

                    xml_required_attr = (field_elem.get('required') or '').strip()
                    xml_required = False

                    if xml_required_attr.lower() in ['1', 'true']:
                        xml_required = True
                    elif 'is_fsm' in xml_required_attr and is_fsm:
                        xml_required = True

                    result['models'][model_name].append({
                        'name': field_name,
                        'string': field_info.get('string', field_name),
                        'type': field_info.get('type', 'char'),
                        'readonly': field_info.get('readonly', False),
                        'required': xml_required or field_info.get('required', False),
                        'is_caching': mobile_config.get('is_caching', False),
                        'caching_refresh_time': mobile_config.get('caching_refresh_time', ''),
                        'is_instant': mobile_config.get('is_instant', False),
                    })

            # Step 5: Add dynamic fields (if applicable)
            sheet_dynamic_fields = {
                field.get('name'): field.get('invisible')
                for field in sheet_fields
                if field.get('name')
            }

            dynamic_fields = request.env['dynamic.fields'].search([
                ('model', '=', model_name),
                ('form_view_id.name', '=', 'end.work.wizard'),
                ('status', '=', 'form')
            ])

            for field in dynamic_fields:
                xml_invisible = sheet_dynamic_fields.get(field.name)

                if not is_fsm and xml_invisible == 'is_fsm':
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
