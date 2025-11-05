from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from dateutil import parser
import logging
from geopy.distance import geodesic
import werkzeug.wrappers

_logger = logging.getLogger(__name__)


class GpsTrackingController(http.Controller):

    @http.route('/web/bulk/sync_gps', type='json', auth='user')
    def gps_bulk_update(self, **kwargs):
        """
        Accepts multiple GPS records in a single call.
        Each record must have: timestamp, latitude, longitude.
        Optionally: employee_id, attendance_id, tracking_type.
        """
        payload = kwargs.get("records")
        if not payload:
            return {'status': 'error', 'message': 'No records provided'}

        current_user = request.env.user
        if not current_user.enable_gps_tracking:
            return {'status': 'error', 'message': 'GPS tracking is disabled for this user'}

        created_ids, errors = [], []

        for i, data in enumerate(payload, start=1):
            try:
                # --- Timestamp required ---
                if not data.get("timestamp"):
                    errors.append({"index": i, "error": "Missing timestamp"})
                    continue

                # --- Validate coordinates ---
                try:
                    latitude = float(data['latitude'])
                    longitude = float(data['longitude'])
                    if not (-90 <= latitude <= 90):
                        raise ValueError("Invalid latitude")
                    if not (-180 <= longitude <= 180):
                        raise ValueError("Invalid longitude")
                except Exception as e:
                    errors.append({"index": i, "error": f"Invalid coordinates: {str(e)}"})
                    continue

                # --- Employee fallback ---
                employee_id = data.get("employee_id")
                if employee_id:
                    employee_id = int(employee_id)
                else:
                    employee_id = current_user.employee_id.id

                # --- Parse timestamp ---
                timestamp_aware = parser.isoparse(data['timestamp'])
                timestamp = timestamp_aware.replace(tzinfo=None)

                # --- Create record ---
                gps_record = request.env['gps.tracking'].sudo().create({
                    'timestamp': timestamp,
                    'latitude': latitude,
                    'longitude': longitude,
                    'employee_id': employee_id,
                    'tracking_type': data.get('tracking_type', 'route_point'),
                    'synced': True,
                    'link_id': False,
                })

                created_ids.append(gps_record.id)

            except Exception as e:
                errors.append({"index": i, "error": str(e)})

        return {
            "status": "OK" if created_ids else "error",
            "created_ids": created_ids,
            "errors": errors,
            "message": f"{len(created_ids)} records created, {len(errors)} failed"
        }

    @http.route('/live/gps/update', type='json', auth='user')
    def gps_update(self, **kwargs):
        data = kwargs
        _logger.info(f"📡 Received GPS data: {data}")

        try:

            # Validate required fields
            current_user = request.env.user
            employee_id = data.get("employee_id")
            if employee_id:
                employee_id = int(employee_id)
            else:
                employee_id = current_user.employee_id.id  # use current user's employee

            if not data.get("timestamp"):
                return {'status': 'error', 'message': 'Missing timestamp'}

            ###############################################################################################
            # Check if current user has GPS tracking enabled

            if not employee_id.user_id.enable_gps_tracking:
                return {'status': 'error', 'message': 'GPS tracking is disabled for this user'}
            ###############################################################################################

            # Validate coordinates
            try:
                latitude = float(data['latitude'])
                longitude = float(data['longitude'])

                if not (-90 <= latitude <= 90):
                    return {'status': 'error', 'message': 'Invalid latitude'}
                if not (-180 <= longitude <= 180):
                    return {'status': 'error', 'message': 'Invalid longitude'}

            except (ValueError, TypeError):
                return {'status': 'error', 'message': 'Invalid coordinate format'}

            # Parse timestamp properly
            timestamp_aware = parser.isoparse(data['timestamp'])
            timestamp = timestamp_aware.replace(tzinfo=None)

            # Check for duplicates within 10-second window
            from_ts = timestamp - timedelta(seconds=5)
            to_ts = timestamp + timedelta(seconds=5)

            domain = [
                ('employee_id', '=', employee_id),
                ('timestamp', '>=', from_ts),
                ('timestamp', '<=', to_ts),
            ]

            exists = request.env['gps.tracking'].sudo().search(domain, limit=1)
            if exists:
                _logger.info("GPS entry already exists within 10-second window")
                return {'status': 'duplicate', 'message': 'Entry already exists'}

            # Validate attendance_id if provided
            attendance_id = data.get('attendance_id')
            if attendance_id:
                try:
                    attendance_id = int(attendance_id)
                    # Verify attendance exists and belongs to employee
                    attendance = request.env['hr.attendance'].sudo().search([
                        ('id', '=', attendance_id),
                        ('employee_id', '=', employee_id)
                    ], limit=1)
                    if not attendance:
                        _logger.warning(f"Attendance {attendance_id} not found for employee {employee_id}")
                        # Don't fail, just log and continue without attendance_id
                        attendance_id = False
                except (ValueError, TypeError):
                    attendance_id = False

            # If no attendance_id provided, try to find active attendance
            if not attendance_id:
                active_attendance = request.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', employee_id),
                    ('check_out', '=', False)
                ], limit=1, order='check_in desc')

                if active_attendance:
                    attendance_id = active_attendance.id
                    _logger.info(f"Found active attendance: {attendance_id}")

            is_suspicious = False
            # Fetch previous point for speed/jump check
            prev_point = request.env['gps.tracking'].sudo().search([
                ('employee_id', '=', employee_id),
                ('timestamp', '<', timestamp)
            ], order='timestamp desc', limit=1)

            if prev_point:
                prev_time = prev_point.timestamp
                prev_lat = prev_point.latitude
                prev_lon = prev_point.longitude
                time_diff = (timestamp - prev_time).total_seconds()
                print("TIME", time_diff)
                if time_diff > 0:
                    dist = geodesic((prev_lat, prev_lon), (latitude, longitude)).meters
                    speed = dist / time_diff  # m/s
                    if speed > 22:
                        is_suspicious = True
                        print("Here i am")
                    if dist > 2000:
                        is_suspicious = True
                        print("Here i am2")
                    if time_diff < 10:
                        is_suspicious = True
                        print("Here i am")
            # Create GPS tracking record
            gps_record = request.env['gps.tracking'].sudo().create({
                'timestamp': timestamp,
                'latitude': latitude,
                'longitude': longitude,
                'employee_id': employee_id,
                'attendance_id': attendance_id or False,
                'tracking_type': data.get('tracking_type', 'route_point'),
                'synced': True,
                'suspicious': is_suspicious,  # <-- new field
                'link_id': False,
            })

            _logger.info(f"✅ Created GPS record {gps_record.id} for employee {employee_id}")
            return {
                'status': 'ok',
                'record_id': gps_record.id,
                'message': 'GPS data saved successfully'
            }

        except Exception as e:
            _logger.error(f"❌ Failed to create GPS record: {str(e)}")
            return {'status': 'error', 'message': f'Server error: {str(e)}'}

    @http.route('/get/google/maps/api/key', type='json', auth='user')
    def get_api_key(self, **kwargs):
        """Get Google Maps API key from system parameters"""
        ###############################################################################################
        data = kwargs
        # Get employee record properly
        employee_id = data.get("employee_id")
        employee = request.env['hr.employee'].sudo().browse(int(employee_id)) if employee_id else None

        # Validate employee and GPS tracking setting
        if not employee or not employee.user_id or not employee.user_id.enable_gps_tracking:
            return {'api_key': '', 'error': 'GPS tracking is disabled for this user'}

        ###############################################################################################
        key = request.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
        if not key:
            _logger.warning("Google Maps API key not configured")
        return {'api_key': key or ''}

    @http.route('/live/gps/get_employee_id', type='json', auth='user')
    def get_employee_id(self):
        """Get current user's employee ID and active attendance ID"""
        try:
            ###############################################################################################
            current_user = request.env.user

            # Check if GPS tracking is enabled for current user
            if not current_user.enable_gps_tracking:
                return {
                    "employee_id": None,
                    "attendance_id": None,
                    "error": "GPS tracking is disabled for this user",
                    "status": "disabled"
                }
            ###############################################################################################

            user_id = request.env.uid
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user_id)], limit=1)

            if not employee:
                return {
                    "employee_id": None,
                    "attendance_id": None,
                    "error": "No employee record found for current user",
                    "status": "error"
                }

            # Fetch active (not checked-out) attendance record
            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1)

            return {
                "employee_id": employee.id,
                "attendance_id": attendance.id if attendance else None,
                "employee_name": employee.name,
                "status": "ok"
            }

        except Exception as e:
            _logger.error(f"Error getting employee and attendance ID: {str(e)}")
            return {
                "employee_id": None,
                "attendance_id": None,
                "error": str(e),
                "status": "error"
            }

    @http.route('/live/gps/path', type='json', auth='user')
    def gps_path(self, date_str, employee_id=None):
        try:
            ############################################################
            current_user = request.env.user
            ############################################################

            user_id = request.env.uid
            if not employee_id:
                #################################################################################
                # Check if current user has GPS tracking enabled
                if not current_user.enable_gps_tracking:
                    return {'error': 'GPS tracking is disabled for this user'}
                ##################################################################################

                employee = request.env['hr.employee'].sudo().search([('user_id', '=', user_id)], limit=1)
            else:
                if isinstance(employee_id, list):
                    employee_id = employee_id[0]
                employee = request.env['hr.employee'].sudo().browse(int(employee_id))
                #########################################################################################
                # Check if the employee's user has GPS tracking enabled
                if employee.user_id and not employee.user_id.enable_gps_tracking:
                    return {'error': 'GPS tracking is disabled for this employee'}
            #########################################################################################

            if not employee:
                return []

            start_dt = f"{date_str} 00:00:00"
            end_dt = f"{date_str} 23:59:59"

            records = request.env['gps.tracking'].sudo().search([
                ('employee_id', '=', employee.id),
                ('timestamp', '>=', start_dt),
                ('timestamp', '<=', end_dt),
            ], order='timestamp')

            # --- New: Calculate speed between check-in and check-out ---
            checkin = records.filtered(lambda r: r.tracking_type == 'check_in')
            checkout = records.filtered(lambda r: r.tracking_type == 'check_out')
            speed_kmh = None
            traveled_duration = None

            if checkin and checkout:
                from geopy.distance import geodesic
                start = checkin[0]
                end = checkout[-1]
                distance = geodesic((start.latitude, start.longitude), (end.latitude, end.longitude)).meters
                duration = (end.timestamp - start.timestamp).total_seconds()
                if duration > 0:
                    speed_kmh = round((distance / 1000) / (duration / 3600), 2)
                    # Format traveled duration as HH:MM:SS
                    hours, remainder = divmod(int(duration), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    traveled_duration = f"{hours:02}:{minutes:02}:{seconds:02}"

            # Build points with optional customer name from source link (dynamic)
            points = []
            for rec in records:
                customer_name = None
                title = None

                try:
                    if rec.link_id:
                        linked = request.env[rec.link_id.model].sudo().browse(rec.link_id.res_id)
                        if linked.exists():
                            # Try to resolve a customer/partner-like field first
                            partner_field_candidates = (
                                'partner_id', 'customer_id', 'commercial_partner_id',
                                'partner', 'res_partner_id', 'contact_id'
                            )
                            partner_record = None
                            for fname in partner_field_candidates:
                                if hasattr(linked, fname):
                                    val = getattr(linked, fname)
                                    if val:
                                        partner_record = val
                                        break

                            if partner_record and hasattr(partner_record, 'name'):
                                customer_name = partner_record.name
                            else:
                                # only set title if customer_name is not found
                                title = getattr(linked, 'display_name', None)
                except Exception:
                    customer_name = None
                    title = None

                points.append({
                    "lat": rec.latitude,
                    "lng": rec.longitude,
                    "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
                    "tracking_type": rec.tracking_type,
                    "attendance_id": rec.attendance_id.id if rec.attendance_id else None,
                    "suspicious": rec.suspicious,
                    "customer_name": customer_name,
                    "title": title,
                })

            return {
                "points": points,
                "speed_kmh": speed_kmh,
                "traveled_duration": traveled_duration,
                "any_suspicious": any(rec.suspicious for rec in records),
            }

        except Exception as e:
            _logger.exception("Error fetching GPS path")
            return []

    @http.route('/live/gps/employees_data', type='json', auth='user')
    def employees_data(self, employee_id=None, date_str=None):
        """Returns employee dropdown + selected employee info"""
        try:
            user = request.env.user
            is_admin = user.has_group('base.group_system')
            employee_model = request.env['hr.employee'].sudo()

            result = {
                "is_admin": is_admin,
                "employee_info": {},
                "employees": [],
            }

            if is_admin:
                # Provide employee list for dropdown
                all_emps = employee_model.search([('user_id', '!=', False)])
                result["employees"] = [{
                    "id": emp.id,
                    "name": emp.name,
                    "image_128": emp.image_128 and f"data:image/png;base64,{emp.image_128.decode()}" or "",
                } for emp in all_emps]

                # Get selected employee info
                if employee_id:
                    employee = employee_model.browse(int(employee_id))
                    ###############################################################################################
                    # Check if selected employee has GPS tracking enabled
                    if not employee.user_id or not employee.user_id.enable_gps_tracking:
                        result["employee_info"] = {"error": "GPS tracking is disabled for this employee"}
                        return result
                ###############################################################################################

                else:
                    result["employee_info"] = {}
                    return result
            else:
                # Not admin – only current employee
                ################################################################################################
                # Not admin – only current employee if GPS tracking is enabled
                if not user.enable_gps_tracking:
                    result["employee_info"] = {"error": "GPS tracking is disabled for this user"}
                    return result
                ################################################################################################

                employee = employee_model.search([('user_id', '=', user.id)], limit=1)

            if not employee:
                result["employee_info"] = {"error": "Employee not found"}
                return result

            # Fetch date-specific info if provided
            total = 0
            if date_str:
                start_dt = f"{date_str} 00:00:00"
                end_dt = f"{date_str} 23:59:59"
                total = request.env['gps.tracking'].sudo().search_count([
                    ('employee_id', '=', employee.id),
                    ('timestamp', '>=', start_dt),
                    ('timestamp', '<=', end_dt),
                ])

            result["employee_info"] = {
                "id": employee.id,
                "name": employee.name,
                "image_128": employee.image_128 and f"data:image/png;base64,{employee.image_128.decode()}" or "",
                "date": date_str,
                "total_points": total,
            }
            return result

        except Exception as e:
            _logger.error(f"❌ Error in employees_data: {str(e)}")
            return {
                "error": str(e)
            }
