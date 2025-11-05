# from odoo import http
# from odoo.http import request
# from lxml import etree
# import json
#
#
# class MobileFieldsController(http.Controller):
#
#     @http.route('/web/mobile_fields', type='json', auth='user')
#     def get_mobile_fields(self):
#         """
#         API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
#         Combines the fields from the model and the view, and filters based on 'for_mobile'.
#         Includes visibility conditions extracted from the view XML using domain, groups, and invisible.
#         """
#         try:
#             request_data = request.httprequest.get_json()
#             model_name = request_data.get('model')
#             view_xml_id = request_data.get('view_xml_id')
#
#             if not model_name or not view_xml_id:
#                 return {'status': 'error', 'message': 'Model and view_xml_id are required'}
#
#             if model_name not in request.env:
#                 return {'status': 'error', 'message': f'Model "{model_name}" does not exist.'}
#
#             # Get model fields
#             model_obj = request.env[model_name]
#             fields_data = model_obj.fields_get()
#
#             # Get view reference
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': 'error', 'message': f'View {view_xml_id} not found'}
#
#             # Get view architecture
#             view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': 'error', 'message': 'View architecture not found'}
#
#             arch_tree = etree.fromstring(arch)
#
#             # Combine fields from model and view
#             model_fields = set(fields_data.keys())
#             view_fields = set(field.get('name') for field in arch_tree.xpath("//field") if field.get('name'))
#             all_fields = model_fields.union(view_fields)
#
#             # Fetch 'for_mobile' fields
#             mobile_field_model = request.env['ir.model.fields.mobile']
#             mobile_fields = {}
#             for_mobile_records = mobile_field_model.search([
#                 ('field_id.model', '=', model_name),
#                 ('for_mobile', '=', True)
#             ])
#
#             # Collect fields marked as 'for_mobile'
#             for_mobile_fields = {rec.field_id.name for rec in for_mobile_records}
#
#             # Process fields for response
#             for field_name in all_fields:
#                 if field_name in for_mobile_fields:
#                     field_info = fields_data.get(field_name, {})
#                     # Find visibility conditions from the view using domain, groups, and invisible
#                     view_field = arch_tree.xpath(f"//field[@name='{field_name}']")
#                     visibility_conditions = None
#                     invisible_condition = None
#
#                     if view_field:
#                         domain = view_field[0].get('domain', None)
#                         groups = view_field[0].get('groups', None)
#                         invisible_condition = view_field[0].get('invisible', None)
#
#                         visibility_conditions = {
#                             'domain': domain,
#                             'groups': groups,
#                             'invisible': invisible_condition
#                         }
#
#                     # Add field info with visibility conditions
#                     mobile_fields[field_name] = {
#                         'type': field_info.get('type'),
#                         'string': field_info.get('string'),
#                         'readonly': field_info.get('readonly'),
#                         'required': field_info.get('required', False),
#                         'selection': field_info.get('selection', []),
#                         'depends': field_info.get('depends', False),
#                         'visibility_conditions': visibility_conditions
#                     }
#
#             return {
#                 'status': 'success',
#                 'fields': mobile_fields
#             }
#
#         except Exception as e:
#             return {'status': 'error', 'message': str(e)}

from odoo import http
from odoo.http import request
from lxml import etree
import json


class MobileFieldsController(http.Controller):

    @http.route('/web/mobile_fields', type='json', auth='user')
    def get_mobile_fields(self):
        """
        API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
        Combines the fields from the model and the view, and filters based on 'for_mobile'.
        Includes visibility conditions extracted from the view XML using domain, groups, and invisible.
        """
        try:
            request_data = request.httprequest.get_json()
            model_name = request_data.get('model')
            view_xml_id = request_data.get('view_xml_id')

            if not model_name or not view_xml_id:
                return {'status': 'error', 'message': 'Model and view_xml_id are required'}

            if model_name not in request.env:
                return {'status': 'error', 'message': f'Model "{model_name}" does not exist.'}

            # Get model fields
            model_obj = request.env[model_name]
            fields_data = model_obj.fields_get()

            # Get view reference
            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': 'error', 'message': f'View {view_xml_id} not found'}

            # Get view architecture
            view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': 'error', 'message': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)

            # Combine fields from model and view (get intersection)
            model_fields = set(fields_data.keys())
            view_fields = set(field.get('name') for field in arch_tree.xpath("//field") if field.get('name'))
            common_fields = model_fields.intersection(view_fields)  # Get only common fields

            # Fetch 'for_mobile' fields
            mobile_field_model = request.env['ir.model.fields.mobile']
            mobile_fields = {}
            for_mobile_records = mobile_field_model.search(
                [('field_id.model', '=', model_name), ('for_mobile', '=', True)])

            # Collect fields marked as 'for_mobile' and present in both model and view
            for_mobile_fields = {rec.field_id.name for rec in for_mobile_records}

            # Process fields for response
            for field_name in common_fields:
                if field_name in for_mobile_fields:
                    field_info = fields_data.get(field_name, {})
                    # Find visibility conditions from the view using domain, groups, and invisible
                    view_field = arch_tree.xpath(f"//field[@name='{field_name}']")
                    visibility_conditions = None
                    invisible_condition = None

                    if view_field:
                        domain = view_field[0].get('domain', None)
                        groups = view_field[0].get('groups', None)
                        invisible_condition = view_field[0].get('invisible', None)

                        visibility_conditions = {
                            'domain': domain,
                            'groups': groups,
                            'invisible': invisible_condition
                        }

                    # Add field info with visibility conditions
                    mobile_fields[field_name] = {
                        'type': field_info.get('type'),
                        'string': field_info.get('string'),
                        'readonly': field_info.get('readonly'),
                        'required': field_info.get('required', False),
                        'selection': field_info.get('selection', []),
                        'depends': field_info.get('depends', False),
                        'visibility_conditions': visibility_conditions
                    }

            return {
                'status': 'success',
                'fields': mobile_fields
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# from odoo import http
# from odoo.http import request
# from lxml import etree
#
#
# class MobileFieldsController(http.Controller):
#
#     @http.route('/web/mobile_fields', type='json', auth='user')
#     def get_mobile_fields(self):
#         """
#         API endpoint to get fields marked as 'for_mobile' for common fields between a given model and a view.
#         Takes model_name and view_xml_id as input in the body.
#         """
#         try:
#             # Get the request data directly using get_json() method
#             request_data = request.httprequest.get_json()
#
#             # Extract model and view_xml_id from the request data
#             model_name = request_data.get('model')
#             view_xml_id = request_data.get('view_xml_id')
#
#             if not model_name or not view_xml_id:
#                 return {'status': 'error', 'message': 'Model and view_xml_id are required'}
#
#             # Ensure the model exists in the environment
#             if model_name not in request.env:
#                 return {'status': 'error', 'message': f'Model "{model_name}" does not exist.'}
#
#             # Get the model and fields data
#             model_obj = request.env[model_name]
#             fields_data = model_obj.fields_get()
#
#             # Get the view reference based on the view_xml_id
#             view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
#             if not view_ref:
#                 return {'status': 'error', 'message': f'View {view_xml_id} not found'}
#
#             # Get view architecture for the given model and view
#             view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
#
#             arch = view_info.get('arch', '')
#             if not arch:
#                 return {'status': 'error', 'message': 'View architecture not found'}
#
#             # Parse the XML architecture
#             arch_tree = etree.fromstring(arch)
#
#             # Extract field names from the view architecture
#             view_fields = [field.get('name') for field in arch_tree.xpath("//field") if field.get('name')]
#
#             # Find the common fields between model fields and view fields
#             common_fields = set(fields_data.keys()).intersection(view_fields)
#
#             # Fetch 'for_mobile' values dynamically for each field
#             mobile_field_model = request.env['ir.model.fields.mobile']
#
#             # Initialize result fields
#             result_fields = {}
#
#             # Iterate through common fields and check if they are marked 'for_mobile=True'
#             for field_name in common_fields:
#                 # Fetch 'for_mobile' value from 'ir.model.fields.mobile'
#                 for_mobile_value = mobile_field_model.get_field_for_mobile(model_name, field_name)
#
#                 if for_mobile_value:
#                     field_info = fields_data[field_name]
#                     result_fields[field_name] = {
#                         'readonly': field_info.get('readonly', False),
#                         'required': field_info.get('required', False),
#                         'string': field_info.get('string', ''),
#                         'type': field_info.get('type', ''),
#                         'widget': '',  # Default empty widget as it comes from view
#                         'domain': field_info.get('domain', []),
#                         'selection': field_info.get('selection', []),
#                         'states': field_info.get('states', {}),
#                         'for_mobile': for_mobile_value  # Include 'for_mobile' value
#                     }
#
#             return {
#                 'status': 'success',
#                 'fields': result_fields
#             }
#
#         except Exception as e:
#             return {'status': 'error', 'message': str(e)}
