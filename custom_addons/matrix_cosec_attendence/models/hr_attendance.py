from odoo import models, api
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def parse_datetime_ist(self, dt_str):
        try:
            dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
            if dt.tzinfo is None:
                ist = pytz.timezone("Asia/Kolkata")
                dt = ist.localize(dt)
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception:
            pass

        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception:
            raise

    @api.model
    def process_matrix_event(self, data):
        """
        Processes a single event from Matrix attendance webhook.
        Includes:
        - timezone conversion
        - dedupe
        - auto-fix in/out mismatch
        """

        user_id = data.get('userid')
        dt_str = data.get('eventdatetime')
        punch_type = str(data.get('entryexittype'))  # "0" or "1"

        # --------------------------------------------------
        # Validate basic input
        # --------------------------------------------------
        if not user_id or not dt_str:
            return {
                "userid": user_id,
                "status": "failed",
                "message": "Missing userid or eventdatetime"
            }

        # --------------------------------------------------
        # Parse + convert timestamp properly
        # --------------------------------------------------
        try:
            dt_utc = self.parse_datetime_ist(dt_str)
        except Exception as e:
            return {
                "userid": user_id,
                "status": "error",
                "message": str(e)
            }

        # --------------------------------------------------
        # Find employee
        # --------------------------------------------------
        employee = self.env['hr.employee'].sudo().search([
            ('x_biometric_id', '=', user_id)
        ], limit=1)

        if not employee:
            return {
                "userid": user_id,
                "status": "failed",
                "message": "Employee not found"
            }

        # --------------------------------------------------
        # DEDUPE CHECK
        # If same punch already exists, skip it
        # --------------------------------------------------
        dup = self.search([
            ('employee_id', '=', employee.id),
            '|',
            ('check_in', '=', dt_utc),
            ('check_out', '=', dt_utc),
        ], limit=1)

        if dup:
            return {
                "userid": user_id,
                "status": "duplicate",
                "record_id": dup.id
            }

        # --------------------------------------------------
        # Handle Check-in (0)
        # --------------------------------------------------
        if punch_type == "0":
            open_att = self.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1)

            # Auto close previous open if exists (self-healing)
            if open_att:
                open_att.write({'check_out': dt_utc})

            rec = self.create({
                'employee_id': employee.id,
                'check_in': dt_utc,
            })

            return {
                "userid": user_id,
                "status": "checkin",
                "record_id": rec.id
            }

        # --------------------------------------------------
        # Handle Check-out (1)
        # --------------------------------------------------
        elif punch_type == "1":

            open_att = self.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ], limit=1)

            # If no open check-in: auto-create one (machine out-of-order punching)
            if not open_att:
                open_att = self.create({
                    'employee_id': employee.id,
                    'check_in': dt_utc,
                })

            open_att.write({'check_out': dt_utc})

            return {
                "userid": user_id,
                "status": "checkout",
                "record_id": open_att.id
            }

        else:
            return {
                "userid": user_id,
                "status": "failed",
                "message": "Invalid entryexittype"
            }
