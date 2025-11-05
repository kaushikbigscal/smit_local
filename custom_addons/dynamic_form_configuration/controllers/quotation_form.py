from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import ast


class QuotationForm(http.Controller):

    @http.route('/web/quotation_form', type='json', auth='user')
    def get_quotation_form(self):
        return self._get_mobile_form_view('sale.order', 'sale.view_order_form')

    def _get_mobile_form_view(self, model_name, view_xml_id):
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

            # Step 2: Get form view architecture
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
                        'is_instant': mobile_config.get('is_instant', False),
                        'widget': field_element.get('widget', ''),
                    })

            # Step 4: Add dynamic fields
            dynamic_fields = request.env['dynamic.fields'].search([
                ('model', '=', model_name),
                ('form_view_id.name', '=', 'sale.order.form'),
                ('status', '=', 'form')
            ])
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
                            "name": field.widget_id.name if field.widget_id else False
                        }
                    },
                    "required": field.required,
                    "readonly": field.readonly,
                    "is_instant": field.is_instant,
                })

            return result

        except Exception as e:
            return {'status': False, 'error': str(e)}
