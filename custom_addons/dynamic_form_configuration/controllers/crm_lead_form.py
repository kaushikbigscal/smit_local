from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import logging, ast

_logger = logging.getLogger(__name__)


class CRMLeadForm(http.Controller):

    @http.route('/web/crm_lead_form/get_lead', type='json', auth='user')
    def get_lead_form(self):
        return self._get_crm_lead_form(lead_type='lead')

    @http.route('/web/crm_lead_form/get_opportunity', type='json', auth='user')
    def get_opportunity_form(self):
        return self._get_crm_lead_form(lead_type='opportunity')

    def _get_crm_lead_form(self, lead_type=None):
        try:
            model_name = "crm.lead"
            view_xml_id = "crm.crm_lead_view_form"

            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': False, 'error': f'View {view_xml_id} not found'}

            model = request.env[model_name]
            view_info = model.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': False, 'error': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)
            sheet_fields = list(arch_tree.iter("field"))
            ordered_fields = OrderedDict()

            for field in sheet_fields:
                field_name = field.get('name')
                if field_name:
                    ordered_fields[field_name] = field

            # Get mobile-enabled fields with caching info
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
                if field_name in mobile_field_map and field_name in fields_data:
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

            # Add dynamic fields
            dynamic_fields = request.env['dynamic.fields'].search([('model', '=', model_name), ('status', '=', 'form')])
            result['dynamic_fields'] = []
            for field in dynamic_fields:
                selection_data = []
                if field.selection_field:
                    try:
                        selection_data = ast.literal_eval(field.selection_field)
                    except Exception:
                        selection_data = []
                result['dynamic_fields'].append({
                    "name": field.name,
                    "field_description": field.field_description,
                    "field_type": field.field_type,
                    "selection_field": selection_data,  # field.selection_field or {},
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
                })

            return result

        except Exception as e:
            _logger.exception("Error fetching CRM lead form")
            return {'status': False, 'error': str(e)}

# from odoo import http
# from odoo.http import request
# from lxml import etree
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class CRMLeadForm(http.Controller):
#
#     def get_crm_lead_form(self, lead_type=None):
#         try:
#             model_name = "crm.lead"
#             view_xml_id = "crm.crm_lead_view_form"
#
#             if not model_name or not view_xml_id:
#                 return {'status': False, 'error': 'Model and view_xml_id are required'}
#
#             model = request.env[model_name]
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': False, 'error': f'View {view_xml_id} not found'}
#
#             view_info = model.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': False, 'error': 'View architecture not found'}
#
#             arch_tree = etree.fromstring(arch)
#             sheet_fields = arch_tree.xpath("//form//sheet//field")
#             sheet_field_names = [field.get('name') for field in sheet_fields if field.get('name')]
#
#             fields_data = model.fields_get()
#             result = {'models': {model_name: []}}
#
#             mobile_field_model = request.env['ir.model.fields.mobile']
#             mobile_fields = {}
#             for_mobile_records = mobile_field_model.search([
#                 ('field_id.model', '=', model_name), ('for_mobile', '=', True)
#             ])
#
#             mobile_field_data = {
#                 record.field_id.name: {
#                     "is_caching": record.is_caching if hasattr(record, 'is_caching') else False,
#                     "caching_refresh_time": record.caching_refresh_time if hasattr(record,
#                                                                                    'caching_refresh_time') else False
#                 }
#                 for record in for_mobile_records if record.field_id
#             }
#
#             processed_field_names = set()
#
#             for field_name in sheet_field_names:
#                 if field_name in fields_data and field_name not in processed_field_names:
#                     field_info = fields_data.get(field_name, {})
#
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
#                     if field_name not in mobile_field_data:
#                         continue
#
#                     if lead_type == 'lead' and isinstance(invisible_condition,
#                                                           str) and 'type == "opportunity"' in invisible_condition:
#                         continue
#                     if lead_type == 'opportunity' and isinstance(invisible_condition,
#                                                                  str) and 'type == "lead"' in invisible_condition:
#                         continue
#
#                     is_caching = mobile_field_data[field_name]['is_caching']
#                     caching_refresh_time = mobile_field_data[field_name][
#                         'caching_refresh_time'] if is_caching else False
#
#                     result['models'][model_name].append({
#                         **{attr: field_info.get(attr, False) for attr in self._get_view_field()},
#                         'invisible': visibility_conditions.get('invisible', False),
#                         'widget': visibility_conditions.get('widget', False),
#                         'is_caching': is_caching,
#                         'caching_refresh_time': caching_refresh_time,
#                     })
#
#                     processed_field_names.add(field_name)
#
#             self._process_groups_and_buttons(arch_tree, lead_type, result, processed_field_names)
#             return result
#
#         except Exception as e:
#             _logger.error("Error fetching CRM lead form: %s", str(e))
#             return {'status': False, 'error': str(e)}
#
#     def _process_groups_and_buttons(self, arch_tree, lead_type, result, processed_field_names):
#         groups = arch_tree.xpath("//group")
#         for group in groups:
#             group_invisible = group.get('invisible', False)
#             if lead_type == 'lead' and isinstance(group_invisible, str) and 'type == "opportunity"' in group_invisible:
#                 continue
#             if lead_type == 'opportunity' and isinstance(group_invisible, str) and 'type == "lead"' in group_invisible:
#                 continue
#
#             group_fields = group.xpath(".//field")
#             for field in group_fields:
#                 field_name = field.get('name')
#                 if field_name and field_name not in processed_field_names:
#                     processed_field_names.add(field_name)
#
#         buttons = arch_tree.xpath("//button")
#         for button in buttons:
#             button_invisible = button.get('invisible', False)
#             if lead_type == 'lead' and isinstance(button_invisible,
#                                                   str) and 'type == "opportunity"' in button_invisible:
#                 continue
#             if lead_type == 'opportunity' and isinstance(button_invisible,
#                                                          str) and 'type == "lead"' in button_invisible:
#                 continue
#
#     def _get_view_field(self):
#         return [
#             'name', 'string', 'type', 'readonly', 'related', 'context', 'depends', 'groups', 'domain', 'help',
#             'relation', 'relation_field', 'required', 'searchable', 'selection'
#         ]
#
#     @http.route('/web/crm_lead_form/get_lead', type='json', auth='user')
#     def get_lead_form(self):
#         return self.get_crm_lead_form(lead_type='lead')
#
#     @http.route('/web/crm_lead_form/get_opportunity', type='json', auth='user')
#     def get_opportunity_form(self):
#         return self.get_crm_lead_form(lead_type='opportunity')

# =========== new requirement ================
# from odoo import http
# from odoo.http import request
# from lxml import etree
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class CRMLeadForm(http.Controller):
#
#     @http.route('/web/crm_lead_form/get_lead', type='json', auth='user')
#     def get_lead_form(self):
#         return self._get_crm_lead_form(lead_type='lead')
#
#     @http.route('/web/crm_lead_form/get_opportunity', type='json', auth='user')
#     def get_opportunity_form(self):
#         return self._get_crm_lead_form(lead_type='opportunity')
#
#     def _get_crm_lead_form(self, lead_type=None):
#         try:
#             model_name = "crm.lead"
#             view_xml_id = "crm.crm_lead_view_form"
#
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': False, 'error': f'View {view_xml_id} not found'}
#
#             view_context = {'default_type': lead_type, 'lang': request.env.user.lang}
#             model = request.env[model_name]
#             view_info = model.with_context(**view_context).get_view(view_ref.id, view_type='form')
#
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': False, 'error': 'View architecture not found'}
#
#             arch_tree = etree.fromstring(arch)
#
#             mobile_fields = request.env['ir.model.fields.mobile'].search([
#                 ('model_id.model', '=', model_name),
#                 ('for_mobile', '=', True)
#             ])
#             mobile_field_map = {
#                 mf.field_id.name: {
#                     'is_caching': mf.is_caching,
#                     'caching_refresh_time': mf.caching_refresh_time
#                 }
#                 for mf in mobile_fields if mf.field_id
#             }
#
#             if not mobile_field_map:
#                 return {'status': False, 'error': 'No mobile fields found for this model'}
#
#             fields_data = model.fields_get()
#             result = {
#                 'models': {
#                     model_name: []
#                 },
#                 'dynamic_fields': []
#             }
#
#             processed_fields = set()
#
#             self._process_fields_from_xml(arch_tree, fields_data, mobile_field_map, result, lead_type, processed_fields)
#
#             dynamic_fields = request.env['dynamic.fields'].search([('model', '=', model_name)])
#             for field in dynamic_fields:
#                 result['dynamic_fields'].append({
#                     "id": field.id,
#                     "status": field.status,
#                     "name": field.name,
#                     "model_id": {
#                         "id": field.model_id.id,
#                         "model": field.model_id.model
#                     } if field.model_id else False,
#                     "field_type": field.field_type,
#                     "selection_field": field.selection_field,
#                     "ref_model_id": {
#                         "id": field.ref_model_id.id,
#                         "model": field.ref_model_id.model
#                     } if field.ref_model_id else False,
#                     "required": field.required,
#                     "model": field.model,
#                     "position_field_id": {
#                         "id": field.position_field_id.id,
#                         "name": field.position_field_id.name
#                     } if field.position_field_id else False,
#                     "position": field.position,
#                     "index": field.index,
#                     "display_name": field.display_name,
#                 })
#
#             return result
#
#         except Exception as e:
#             _logger.exception("Error fetching CRM lead form")
#             return {'status': False, 'error': str(e)}
#
#     def _process_fields_from_xml(self, arch_tree, fields_data, mobile_field_map, result, lead_type, processed_fields):
#         for element in arch_tree.iter():
#             if element.tag == 'field':
#                 field_name = element.get('name')
#                 if not field_name or field_name in processed_fields or field_name not in mobile_field_map or field_name not in fields_data:
#                     continue
#
#                 invisible_attr = element.get('invisible', 'False')
#                 if not self._is_field_visible(invisible_attr, lead_type):
#                     continue
#
#                 field_info = fields_data[field_name]
#                 mobile_config = mobile_field_map[field_name]
#
#                 field_data = {
#                     'name': field_name,
#                     'string': field_info.get('string', field_name),
#                     'type': field_info.get('type', 'char'),
#                     'readonly': field_info.get('readonly', False),
#                     'is_caching': mobile_config.get('is_caching', False),
#                     'caching_refresh_time': mobile_config.get('caching_refresh_time', ''),
#                 }
#
#                 result['models']['crm.lead'].append(field_data)
#                 processed_fields.add(field_name)
#
#     def _is_field_visible(self, invisible_attr, lead_type):
#         if invisible_attr == 'False' or invisible_attr == '0':
#             return True
#         try:
#             if "type == 'lead'" in invisible_attr and lead_type == 'lead':
#                 return False
#             if "type == 'opportunity'" in invisible_attr and lead_type == 'opportunity':
#                 return False
#             if "not type == 'lead'" in invisible_attr and lead_type == 'opportunity':
#                 return True
#             if "not type == 'opportunity'" in invisible_attr and lead_type == 'lead':
#                 return True
#             if "type == 'lead'" in invisible_attr:
#                 return lead_type != 'lead'
#             if "type == 'opportunity'" in invisible_attr:
#                 return lead_type != 'opportunity'
#             return True
#         except Exception:
#             _logger.exception(f"Error evaluating invisibility condition: {invisible_attr}")
#             return True
