# controller/ main.py

import requests
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessDenied
import logging

_logger = logging.getLogger(__name__)


class AuthController(http.Controller):

    # controller/main.py - Updated debug_authenticate method with detailed debugging

    @http.route('/web/debug_auth', type='http', auth="none", methods=['POST'], csrf=False)
    def debug_authenticate(self, **post):
        """Working debug authentication endpoint"""
        try:
            # Debug print to confirm endpoint is hit
            _logger.info("DEBUG AUTH ENDPOINT CALLED - RAW POST DATA: %s", post)
            # print("DEBUG AUTH ENDPOINT CALLED - RAW POST DATA:", post)

            # Get all parameters
            db = post.get('db') or request.session.db
            login = post.get('login')
            password = post.get('password')
            debug_token = post.get('debug_token')
            redirect = post.get('redirect', '/web')

            _logger.info(f"Debug auth attempt for {login} (DB: {db})")

            # Validate required fields
            if not all([db, login, password, debug_token]):
                _logger.warning("Missing required fields")
                return request.redirect('/web/login?error=missing_fields&device_lock_debug=1')

            # Standard authentication
            uid = request.session.authenticate(db, login, password)
            if not uid:
                _logger.warning("Standard authentication failed")
                return request.redirect('/web/login?error=auth_failed&device_lock_debug=1')

            # Verify debug token
            user = request.env['res.users'].browse(uid)
            if not user.debug_access_token or user.debug_access_token.strip() != debug_token.strip():
                request.session.logout()
                _logger.warning(f"Debug token mismatch. Expected: {user.debug_access_token}, Got: {debug_token}")
                return request.redirect('/web/login?error=invalid_token&device_lock_debug=1')

            # Update last used timestamp & Clear device login token
            user.update_debug_token_usage()

            # Success
            request.session['debug_mode'] = True
            _logger.info("Debug authentication successful!")
            return request.redirect(redirect)

        except Exception as e:
            _logger.error("Debug auth error: %s", str(e), exc_info=True)
            return request.redirect('/web/login?error=system_error&device_lock_debug=1')


class DeviceSecurityController(http.Controller):

    @http.route('/device/register', type='json', auth='user', methods=['POST'])
    def register_device(self, device_uuid, login_type='web', device_info=None):
        """
        Register or validate the device UUID for the current user.
        login_type: 'web' or 'mobile'
        device_info: Dictionary containing device information
        """
        try:
            env = request.env
            user = env.user
            company = user.company_id

            """Skip device validation if in debug mode"""
            # Bypass if debug mode is active
            if request.session.get('debug_mode'):
                _logger.info(f"Device lock skip for Debug Mode for user {user.name}")
                return {'status': 'ok', 'message': 'Debug mode active - validation skipped'}

            # Check if device lock is enabled at company level
            if not company.device_lock_enabled:
                _logger.info(f"Device lock not enabled for company {company.name}")
                # Still update device info even if lock is disabled
                if device_info:
                    self._update_user_device_info(device_info)
                return {'status': 'ok', 'message': 'Device lock not enforced'}

            # Bypass for system admin
            is_admin = user.id == 1 or user.has_group('base.group_system')
            if is_admin:
                _logger.info(f"Bypassing device lock for system admin {user.login}")
                if device_info:
                    self._update_user_device_info(device_info)
                return {'status': 'ok', 'message': 'Device lock not enforced for system admin'}

            # Validate input
            if not device_uuid:
                raise AccessDenied("Device UUID is required")

            restriction = user.login_restriction or 'none'
            if restriction == 'none':
                _logger.info(f"Login restriction is 'none' for user {user.login}. Skipping device lock.")
                if device_info:
                    self._update_user_device_info(device_info)
                return {'status': 'ok', 'message': 'Device lock not enforced due to no restriction'}

            if restriction != login_type:
                _logger.warning(
                    f"Login type '{login_type}' not allowed for user {user.login} with restriction '{restriction}'")
                raise AccessDenied(f"Login type '{login_type}' not allowed for user {user.login}.")

            # Find existing lock
            lock = env['user.device.lock'].sudo().search([('user_id', '=', user.id)], limit=1)
            is_first_login = False

            if lock:
                if not lock.device_uuid:
                    # Admin has reset the device; allow saving the new UUID
                    lock.sudo().write({
                        'device_uuid': device_uuid,
                        'last_used': fields.Datetime.now(),
                        'login_type': login_type,
                    })
                    is_first_login = True
                    _logger.info(f"Device UUID set after admin reset for user {user.login}")
                elif lock.device_uuid != device_uuid:
                    _logger.warning(
                        f"Device mismatch for user {user.login}: expected {lock.device_uuid}, got {device_uuid}")
                    raise AccessDenied("Device not recognized. Please contact your administrator.")
                else:
                    # Existing valid device
                    lock.sudo().write({
                        'last_used': fields.Datetime.now(),
                        'login_type': login_type,
                    })
            else:
                # No lock exists yet: first-time registration
                env['user.device.lock'].sudo().create({
                    'user_id': user.id,
                    'device_uuid': device_uuid,
                    'last_used': fields.Datetime.now(),
                    'login_type': login_type,
                })
                is_first_login = True
                _logger.info(f"New device registered for user {user.login}")

            # Update device information
            if device_info:
                self._update_user_device_info(device_info)

            message = 'Device registered successfully for first login after reset' if is_first_login else 'Device validated successfully'
            return {'status': 'ok', 'message': message}

        except AccessDenied:
            raise
        except Exception as e:
            _logger.error(f"Error in device registration: {str(e)}", exc_info=True)
            raise AccessDenied("Device registration failed")

    def _update_user_device_info(self, device_info):
        """
        Update or create device information for the current user
        """
        try:
            env = request.env
            user = env.user

            if not device_info:
                return

            # Find existing device info record
            info_model = env['user.device.info']
            existing_record = info_model.sudo().search([('user_id', '=', user.id)], limit=1)

            # Prepare device data with safety checks
            device_data = {
                'user_id': user.id,
                'device_os': self._safe_get(device_info, 'os', 255),
                'device_browser': self._safe_get(device_info, 'browser', 255),
                'device_user_agent': self._safe_get(device_info, 'user_agent', 1000),
                'device_platform': self._safe_get(device_info, 'platform', 255),
                'device_vendor': self._safe_get(device_info, 'vendor', 255),
                'device_model': self._safe_get(device_info, 'device_model', 255),
                'device_type': self._safe_get(device_info, 'device_type', 50),
                'screen_resolution': self._safe_get(device_info, 'screen_resolution', 50),
                'timezone': self._safe_get(device_info, 'timezone', 100),
                'language': self._safe_get(device_info, 'language', 10),
                'last_updated': fields.Datetime.now(),
                'client_ip': self.fetch_client_ip(),
            }

            if existing_record:
                existing_record.sudo().write(device_data)
                _logger.info(f"Updated device info for user {user.login}")
            else:
                info_model.sudo().create(device_data)
                _logger.info(f"Created device info record for user {user.login}")

        except Exception as e:
            _logger.warning(f"Could not update user device info for {user.login}: {str(e)}")

    def _safe_get(self, data, key, max_length=None):
        """
        Safely extract data with length validation
        """
        value = data.get(key, '')
        if not value:
            return ''

        value = str(value)
        if max_length and len(value) > max_length:
            value = value[:max_length]

        return value

    def fetch_client_ip(self):
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            _logger.error("Failed to fetch IP: %s", str(e))
            return False
