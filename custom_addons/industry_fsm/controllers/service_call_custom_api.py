from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class SerialNumberController(http.Controller):

    @http.route('/web/call/serial_numbers_by_customer_product', type='json', auth='user')
    def get_serials_by_customer_and_product(self, customer_id, product_id):
        if not customer_id or not product_id:
            return {'error': 'Missing customer_id or product_id'}

        # Fetch product and customer
        customer = request.env['res.partner'].sudo().browse(customer_id)
        product = request.env['product.product'].sudo().browse(product_id)
        if not customer.exists() or not product.exists():
            return {'error': 'Invalid customer or product'}

        # Find relevant sale lines
        sale_lines = request.env['sale.order.line'].sudo().search([
            ('order_id.partner_id', '=', customer.id),
            ('product_id', '=', product.id)
        ])

        response_data = []

        for line in sale_lines:
            serials = request.env['stock.lot'].sudo().browse([])

            # Related pickings
            pickings = request.env['stock.picking'].sudo().search([
                ('sale_id', '=', line.order_id.id)
            ])

            # Fetch sale order related fields: warranty_start_date, warranty_end_date, unit_status
            sale_order = line.order_id
            warranty_start_date = sale_order.warranty_start_date
            warranty_end_date = line.line_warranty_end_date  # Correct the reference to `warranty_end_date`
            unit_status = line.unit_status  # Correct the reference to `unit_status`

            if not product.is_part:
                # Get serials from stock move lines
                move_lines = request.env['stock.move.line'].sudo().search([
                    ('picking_id', 'in', pickings.ids),
                    ('product_id', '=', product.id),
                    ('lot_id', '!=', False)
                ])
                serials |= move_lines.mapped('lot_id')

                # Get serials from picking parts
                for picking in pickings:
                    for part in picking.picking_parts_ids:
                        if part.lot_ids:
                            serials |= part.lot_ids
            else:
                # If part, match product in parts
                for picking in pickings:
                    for part in picking.picking_parts_ids:
                        if part.original_product_id == product and part.lot_ids:
                            serials |= part.lot_ids

            # Construct the response for each sale order
            serial_numbers = [{'id': lot.id, 'name': lot.name} for lot in serials]

            response_data.append({
                'id': sale_order.id,
                'name': line.display_name,
                'serial_numbers': serial_numbers,
                'unit_status': unit_status,
                'warranty_start_date': warranty_start_date,
                'warranty_end_date': warranty_end_date
            })

        return response_data


class ProductFetchController(http.Controller):

    @http.route('/web/fetch_available_products', type='json', auth='user')
    def fetch_available_products(self, customer_id):
        product = request.env['product.product'].sudo()
        sale_order_line = request.env['sale.order.line'].sudo()
        available_products = product.browse([])

        if customer_id:
            sale_lines = sale_order_line.search([
                ('order_id.partner_id', '=', int(customer_id))
            ])
            available_products = sale_lines.mapped('product_id')

        product_data = [{
            'id': p.id,
            'name': p.name,
            'category': [p.categ_id.id, p.categ_id.name],

        } for p in available_products]

        return {
            'products': product_data
        }

class ServiceCallConfig(http.Controller):
    @http.route('/web/get/service_call_config', type='json', auth='user')
    def get_service_call_flags(self):
        try:
            user = request.env.user
            company = request.env.company
            config = request.env['ir.config_parameter'].sudo()

            # User-Level Flags
            user_level_flags = {
                'enable_geofence_service': bool(getattr(user, 'enable_geofence_service', False)),
                'enable_geofencing_on_checkin': bool(getattr(company, 'enable_geofencing_on_checkin', False)),
                'enable_geofencing_on_checkout': bool(getattr(company, 'enable_geofencing_on_checkout', False)),
            }

            # Company-Level Flags
            company_level_flags = {
                'resolved_required_fields': [field.field_description for field in
                                             getattr(company, 'resolved_required_fields', [])],
                'attachment_required': bool(getattr(company, 'attachment_required', False)),
                'signed_required': bool(getattr(company, 'signed_required', False)),
                'enable_geofence_service': bool(getattr(company, 'enable_geofence_service', False)),
                'allowed_distance_service': float(getattr(company, 'allowed_distance_service', 0.0)),
                'enable_geofencing_on_checkin': bool(getattr(company, 'enable_geofencing_on_checkin', False)),
                'enable_geofencing_on_checkout': bool(getattr(company, 'enable_geofencing_on_checkout', False)),
            }

            # System Setting Flags
            setting_flags = {
                'service_planned_stage': bool(config.get_param('industry_fsm.service_planned_stage', False)),
                'service_resolved_stage': bool(config.get_param('industry_fsm.service_resolved_stage', False))
            }

            # Determine Service Call Role
            service_call_role = 'none'
            try:
                if user.has_group('industry_fsm.group_fsm_manager'):
                    service_call_role = 'admin'
                elif user.has_group('industry_fsm.group_fsm_supervisor'):
                    service_call_role = 'supervisor'
                elif user.has_group('industry_fsm.group_fsm_user'):
                    service_call_role = 'user'
            except Exception as e:
                _logger.error(f"Error checking service call role: {str(e)}", exc_info=True)

            return {
                'user_level_flags': user_level_flags,
                'company_level_flags': company_level_flags,
                'setting_flags': setting_flags,
                'service_call_role': service_call_role,
            }

        except Exception as e:
            _logger.error(f"Error fetching service call configuration: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e)
            }


class FSMUserListController(http.Controller):

    @http.route('/web/call/user_pending_calls', type='json', auth='user', methods=['POST'])
    def get_pending_calls(self, **kwargs):
        """
        Call this endpoint with JSON body:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "department_id": 9
                },
                "id": 1
            }
        """
        department_id = kwargs.get('department_id')
        result = request.env['res.users'].sudo().get_fsm_pending_calls_by_user(department_id=department_id)
        return {
            'status': 'success',
            'data': result
        }
