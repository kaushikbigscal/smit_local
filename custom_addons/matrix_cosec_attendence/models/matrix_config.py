
from odoo import models, fields, api
from datetime import datetime, timedelta
import requests
import logging
import pytz

_logger = logging.getLogger(__name__)


class MatrixConfiguration(models.Model):
    _name = 'matrix.configuration'
    _description = 'Matrix Biometric Configuration'

    name = fields.Char(string='Name', required=True)
    api_url = fields.Char(string='API URL', required=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    # date_from = fields.Char('Date From', default='01042023000000', help="Format: DDMMYYYYHHMMSS")
    # date_to = fields.Char('Date To', default='25042024235959', help="Format: DDMMYYYYHHMMSS")
    active = fields.Boolean(default=True)
    last_sync_date = fields.Datetime('Last Sync Date')
    date_from=fields.Date(string='Date From')
    date_to=fields.Date(string='Date To')


    def _get_auth(self):
        _logger.debug("Preparing authentication details for Matrix API.")
        return requests.auth.HTTPBasicAuth(self.username, self.password)

    def get_date_range(self):
        # Check if called from scheduled action (context flag)
        is_scheduled = self.env.context.get('from_cron', False)

        if not is_scheduled and self.date_from and self.date_to:
            start_of_day = datetime.combine(self.date_from, datetime.min.time())
            end_of_day = datetime.combine(self.date_to, datetime.max.time()).replace(microsecond=0)
        else:
            # Use current day
            start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(hours=23, minutes=59, seconds=59)

        # Format the dates in DDMMYYYYHHMMSS
        date_from = start_of_day.strftime("%d%m%Y%H%M%S")
        date_to = end_of_day.strftime("%d%m%Y%H%M%S")

        # Generate the date range string
        date_range = f"{date_from}-{date_to}"

        _logger.debug(f"Generated date range for sync: {date_range}")
        return date_range

    def action_sync_attendance(self):
        self.ensure_one()
        self.env['matrix.attendance.sync']._sync_attendance()


class MatrixAttendanceSync(models.Model):
    _name = 'matrix.attendance.sync'
    _description = 'Matrix Attendance Sync'

    @api.model
    def _sync_attendance(self):
        _logger.info("Starting Matrix attendance sync process.")
        config = self.env['matrix.configuration'].search([('active', '=', True)], limit=1)
        if not config:
            _logger.error("Matrix configuration not found! Sync process aborted.")
            return

        date_range = config.get_date_range()
        url = f"{config.api_url}?action=get;date-range={date_range};format=json"
        _logger.info(f"Using date range: {date_range} for attendance data sync.")
        _logger.info(f"URL is {url}")

        try:
            response = requests.get(
                url,
                auth=config._get_auth(),
                timeout=30
            )
        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error during attendance sync: {str(e)}")
            # Log network errors in server error log
            self.env['matrix.server.error.log'].create({
                'event_datetime': fields.Datetime.now(),
                'reason': f"Network error: {str(e)}",
                'api_status_code': False,
            })
            return

        if response.status_code == 200:
            try:
                attendance_data = response.json().get('event-ta-date', [])
                _logger.info(f"Retrieved {len(attendance_data)} attendance records from the Matrix API.")

                # Initialize the IST timezone
                ist_tz = pytz.timezone('Asia/Kolkata')

                # Group attendance records by user and sort by datetime to ensure the correct check-in/out pairing
                grouped_attendance = {}
                for record in attendance_data:
                    userid = record['userid']
                    username = record['username']
                    event_datetime = datetime.strptime(record['eventdatetime'], '%d/%m/%Y %H:%M:%S')
                    event_datetime = ist_tz.localize(event_datetime).astimezone(pytz.utc).replace(
                        tzinfo=None)  # Convert to UTC
                    date_key = event_datetime.date()

                    grouped_attendance.setdefault(userid, {}).setdefault(date_key, []).append({
                        'eventdatetime': event_datetime,
                        'entryexittype': record['entryexittype'],
                        'username': username
                    })

                for userid, dates in grouped_attendance.items():
                    for event_date, events in dates.items():
                        events.sort(key=lambda x: x['eventdatetime'])
                        employee = self.env['hr.employee'].search([('x_biometric_id', '=', userid),('disable_tracking', '=', False)], limit=1)

                        if not employee:
                            _logger.warning(f"Employee not found for biometric ID: {userid}")
                            for event in events:
                                self.env['matrix.attendance.log'].create({
                                    'employee_id': False,
                                    'biometric_id': userid,
                                    'event_datetime': event['eventdatetime'],
                                    'entry_exit_type': event['entryexittype'],
                                    'reason': 'Employee not found for this biometric ID',
                                    'username': event['username']
                                })
                            continue

                        # Get first meaningful check_in and last check_out logic
                        check_in = None
                        check_out = None
                        first = events[0]
                        last = events[-1]

                        # First IN or OUT is treated as check_in
                        if first['entryexittype'] in ['0', '1']:
                            check_in = first['eventdatetime']

                        # Last IN or OUT is treated as check_out, only if it comes after check_in
                        if last['eventdatetime'] > check_in:
                            check_out = last['eventdatetime']
                        else:
                            check_out = check_in  # fallback

                        # If only one punch for the day
                        if len(events) == 1:
                            self.env['matrix.attendance.log'].create({
                                'employee_id': employee.id,
                                'biometric_id': userid,
                                'event_datetime': first['eventdatetime'],
                                'entry_exit_type': first['entryexittype'],
                                'reason': 'Only one punch for the day',
                                'username': first['username']
                            })
                            continue

                        # Prevent duplicate attendance
                        existing_attendance = self.env['hr.attendance'].search([
                            ('employee_id', '=', employee.id),
                            ('check_in', '=', check_in),
                        ], limit=1)

                        if not existing_attendance:
                            attendance = self.env['hr.attendance'].create({
                                'employee_id': employee.id,
                                'check_in': check_in,
                                'check_out': check_out,
                            })

                            if check_in == check_out:
                                # Log same in/out as invalid
                                self.env['matrix.attendance.log'].create({
                                    'employee_id': employee.id,
                                    'biometric_id': userid,
                                    'event_datetime': check_in,
                                    'entry_exit_type': first['entryexittype'],
                                    'reason': 'Same Check-in and Check-out Time',
                                    'username': first['username']
                                })
                                attendance.unlink()
                config.last_sync_date = fields.Datetime.now()
                _logger.info("Matrix attendance sync process completed successfully.")

            except Exception as e:
                _logger.error(f"An error occurred during attendance processing: {str(e)}")
                self.env['matrix.server.error.log'].create({
                    'event_datetime': fields.Datetime.now(),
                    'reason': f"Processing error: {str(e)}",
                    'api_status_code': response.status_code,
                })
        else:
            # Non-200 response, log error in matrix.server.error.log
            _logger.error(f"Matrix API returned status code {response.status_code}: {response.text}")
            self.env['matrix.server.error.log'].create({
                'event_datetime': fields.Datetime.now(),
                'reason': f"HTTP {response.status_code} error: {response.text}",
                'api_status_code': response.status_code,
            })

