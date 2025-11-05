from odoo import models, fields, api
from datetime import date,datetime,timedelta,time
import pytz
import logging

_logger = logging.getLogger(__name__)

class EmployeeCertification(models.Model):
    _name = 'employee.certification'
    _description = 'Employee Certification'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Certification Name', required=True, tracking=True)
    certification_date = fields.Date(string='Certification Date', required=True, tracking=True)
    # expiry_date = fields.Date(string='Expiry Date', required=True, tracking=True)
    expiry_date_time = fields.Datetime(string='Expiry date & Time', help='Time of day when the certification expires (24-hour format)', tracking=True, required=True)

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    state = fields.Selection(
        [('valid', 'Valid'), ('expired', 'Expired')],
        string='Status', compute='_compute_state', store=True)
    certificate_file = fields.Binary(string='Certificate Image', required=True, tracking=True)


    # @api.depends('expiry_date')
    # def _compute_state(self):
    #     for record in self:
    #         if record.expiry_date and record.expiry_date < date.today():
    #             record.state = 'expired'
    #         else:
    #             record.state = 'valid'

    @api.depends('expiry_date_time')
    def _compute_state(self):
        current_time_ist = datetime.now()  # Current time in IST

        for record in self:
            if record.expiry_date_time and record.expiry_date_time < current_time_ist:

                record.state = 'expired'
            else:
                record.state = 'valid'

    def update_certification_status(self):
        """Update certification status based on expiry date and time."""
        certifications = self.search([])  # Fetch all certification records
        ist_timezone = pytz.timezone('Asia/Kolkata')  # Timezone for India
        current_time_ist = datetime.now(ist_timezone)  # Current time in IST

        _logger.info("Starting certification status update...")

        for record in certifications:
            previous_state = record.state

            # Convert the record's expiry date to the IST timezone
            if record.expiry_date_time:
                expiry_date_ist = record.expiry_date_time.astimezone(ist_timezone)

                # Check if the expiry date has passed
                if expiry_date_ist < current_time_ist:
                    record.state = 'expired'
                else:
                    record.state = 'valid'

                # Log state changes
                if record.state != previous_state:
                    _logger.info(f"Certification {record.name} updated from {previous_state} to {record.state} at {current_time_ist}.")
                else:
                    _logger.info(f"Certification {record.name} state remains {record.state} at {current_time_ist}.")

   