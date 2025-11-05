from odoo import models, fields, api


class GpsTracking(models.Model):
    _name = 'gps.tracking'
    _description = 'Employee GPS Tracking Data'
    _order = 'timestamp asc'

    timestamp = fields.Datetime(default=fields.Datetime.now)
    latitude = fields.Float(string='Latitude', digits=(16, 6))
    longitude = fields.Float(string='Longitude', digits=(16, 6))
    employee_id = fields.Many2one('hr.employee', string='Employee')
    attendance_id = fields.Many2one('hr.attendance', string='Attendance')
    synced = fields.Boolean(default=False)
    tracking_type = fields.Selection([
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('call_start', 'Work Start'),
        ('call_end', 'Work End'),
        ('route_point', 'Route Point'),
    ], default='route_point', string='Tracking Type', required=True)

    # Centralized dynamic source link (replaces specific lead/task/visit fields)
    link_id = fields.Many2one('tracking.source.link', string='Source Link', index=True, readonly=True)
    address = fields.Char(string="Address")

    suspicious = fields.Boolean(string='Suspicious Point', default=False)

    def action_export_tracking(self):
        ids = ",".join(map(str, self.ids))
        url = f"/gps/tracking/export?ids={ids}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    @api.model
    def create_route_point(self, employee_id, latitude, longitude, tracking_type='route_point', address='',
                           source_model=None, source_record_id=None):
        """Create a new route tracking point"""
        employee = self.env['hr.employee'].browse(employee_id)

        ###################################################################################
        # Check if employee has a user and GPS tracking is enabled
        if not employee.user_id or not employee.user_id.enable_gps_tracking:
            print(f"GPS tracking is disabled for employee {employee.name}")
            return False
        ###################################################################################

        # Get current active attendance session
        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', employee_id),
            ('check_out', '=', False)
        ], limit=1)

        # Create/find centralized source link if provided
        link = False
        if source_model and source_record_id:
            link = self.env['tracking.source.link']._get_or_create_link(source_model, int(source_record_id))

        vals = {
            'employee_id': employee_id,
            'attendance_id': attendance.id if attendance else False,
            'latitude': latitude,
            'longitude': longitude,
            'tracking_type': tracking_type,
            'timestamp': fields.Datetime.now(),
            'address': address,
            'link_id': link.id if link else False,
        }
        return self.create(vals)

    # ----------------------------------------------------------------------------------
    # Enforce: remove route points that occur after last check_out of the day
    # ----------------------------------------------------------------------------------
    # def _cleanup_route_points_after_checkout(self, employee_id, ts):
    #     if not employee_id or not ts:
    #         return
    #     # Compute the start/end of day as strings to match existing usage
    #     date_str = ts.strftime('%Y-%m-%d')
    #     start_dt = f"{date_str} 00:00:00"
    #     end_dt = f"{date_str} 23:59:59"
    #
    #     # Find last check_out for that day
    #     last_checkout = self.search([
    #         ('employee_id', '=', employee_id),
    #         ('tracking_type', '=', 'check_out'),
    #         ('timestamp', '>=', start_dt),
    #         ('timestamp', '<=', end_dt),
    #     ], order='timestamp desc', limit=1)
    #
    #     if last_checkout and last_checkout.timestamp:
    #         offenders = self.search([
    #             ('employee_id', '=', employee_id),
    #             ('tracking_type', '=', 'route_point'),
    #             ('timestamp', '>', last_checkout.timestamp),
    #             ('timestamp', '>=', start_dt),
    #             ('timestamp', '<=', end_dt),
    #         ])
    #         if offenders:
    #             offenders.unlink()
    #
    # @api.model
    # def create(self, vals):
    #     # Support both single dict and list of dicts
    #     if isinstance(vals, list):
    #         records = super().create(vals)
    #         for rec in records:
    #             try:
    #                 self._cleanup_route_points_after_checkout(rec.employee_id.id, rec.timestamp)
    #             except Exception:
    #                 continue
    #         return records
    #     else:
    #         rec = super().create(vals)
    #         try:
    #             self._cleanup_route_points_after_checkout(rec.employee_id.id, rec.timestamp)
    #         except Exception:
    #             pass
    #         return rec


# Extend existing models to integrate tracking
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        """Override create to add route tracking"""
        attendance = super().create(vals)
        # Create route tracking point for check-in
        if ('check_in' in vals and vals.get('in_latitude') and vals.get('in_longitude')
                #######################################################################################################
                and attendance.employee_id.user_id and attendance.employee_id.user_id.enable_gps_tracking):
            #######################################################################################################
            self.env['gps.tracking'].create_route_point(
                employee_id=attendance.employee_id.id,
                latitude=vals['in_latitude'],
                longitude=vals['in_longitude'],
                tracking_type='check_in',
                address=attendance.check_in_address if attendance.check_in_address else ""
            )

        return attendance

    def write(self, vals):
        """Override write to handle check-out tracking"""
        result = super().write(vals)

        # Create route tracking point for check-out
        if 'check_out' in vals and vals.get('out_latitude') and vals.get('out_longitude'):
            for attendance in self:
                ##########################################################################################
                if (attendance.employee_id.user_id and
                        attendance.employee_id.user_id.enable_gps_tracking):
                    ###########################################################################################
                    self.env['gps.tracking'].create_route_point(
                        employee_id=attendance.employee_id.id,
                        latitude=vals['out_latitude'],
                        longitude=vals['out_longitude'],
                        tracking_type='check_out',
                        address=attendance.check_out_address if attendance.check_out_address else ""
                    )

        return result


#################################################################################################
class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_gps_tracking = fields.Boolean(
        string='Enable GPS Tracking',
        default=False,
        help='Enable GPS tracking for this user. When disabled, the user will not be able to send GPS data or view tracking information.'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    time_interval = fields.Integer(string="Time Interval(ms)", default=5000,
                                   help='Time between gps auto fetch in milliseconds.')

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'field_service_tracking.time_interval', self.time_interval
        )

    @api.model
    def get_values(self):
        res = super().get_values()
        res.update(
            time_interval=int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'field_service_tracking.time_interval', default=5000
                )
            )
        )
        return res


#################################################################################################


class TrackingSourceLink(models.Model):
    _name = 'tracking.source.link'
    _description = 'Centralized source link for GPS/Timesheet activities'
    _rec_name = 'display_name'

    model_id = fields.Many2one('ir.model', string='Model', required=True, index=True, ondelete='cascade')
    model = fields.Char(related='model_id.model', string='Model Technical Name', store=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    display_name = fields.Char(string='Name', compute='_compute_display_name', store=False)

    _sql_constraints = [
        ('model_res_unique', 'unique(model_id, res_id)', 'A link for this record already exists.'),
    ]

    @api.depends('model_id', 'res_id')
    def _compute_display_name(self):
        for rec in self:
            name = ''
            try:
                if rec.model_id and rec.res_id:
                    rec_model = self.env[rec.model_id.model]
                    rec_record = rec_model.browse(rec.res_id)
                    if rec_record.exists():
                        name = rec_record.display_name
            except Exception:
                name = ''
            rec.display_name = name

    def name_get(self):
        result = []
        for rec in self:
            model_name = rec.model_id.name or rec.model or 'Record'
            result.append((rec.id, f"{model_name}: {rec.display_name or rec.res_id}"))
        return result

    @api.model
    def _get_or_create_link(self, model, res_id):
        model_id = self.env['ir.model']._get_id(model)
        link = self.search([('model_id', '=', model_id), ('res_id', '=', int(res_id))], limit=1)
        if link:
            return link
        return self.create({'model_id': model_id, 'res_id': int(res_id)})

# from odoo import models, fields, api
#
#
# class GpsTracking(models.Model):
#     _name = 'gps.tracking'
#     _description = 'Employee GPS Tracking Data'
#     _order = 'timestamp asc'
#
#     timestamp = fields.Datetime(default=fields.Datetime.now)
#     latitude = fields.Float(string='Latitude', digits=(16, 6))
#     longitude = fields.Float(string='Longitude', digits=(16, 6))
#     employee_id = fields.Many2one('hr.employee', string='Employee')
#     attendance_id = fields.Many2one('hr.attendance', string='Attendance')
#     synced = fields.Boolean(default=False)
#     tracking_type = fields.Selection([
#         ('check_in', 'Check In'),
#         ('check_out', 'Check Out'),
#         ('call_start', 'Work Start'),
#         ('call_end', 'Work End'),
#         ('route_point', 'Route Point'),
#     ], default='route_point', string='Tracking Type', required=True)
#
#     lead_id = fields.Many2one('crm.lead', string="Lead/Opportunity")
#     address = fields.Char(string="Address")
#
#     suspicious = fields.Boolean(string='Suspicious Point', default=False)
#
#     def action_export_tracking(self):
#         ids = ",".join(map(str, self.ids))
#         url = f"/gps/tracking/export?ids={ids}"
#         return {
#             'type': 'ir.actions.act_url',
#             'url': url,
#             'target': 'self',
#         }
#
#     @api.model
#     def create_route_point(self, employee_id, latitude, longitude, tracking_type='route_point', address=''):
#         """Create a new route tracking point"""
#         employee = self.env['hr.employee'].browse(employee_id)
#
#         ###################################################################################
#         # Check if employee has a user and GPS tracking is enabled
#         if not employee.user_id or not employee.user_id.enable_gps_tracking:
#             print(f"GPS tracking is disabled for employee {employee.name}")
#             return False
#         ###################################################################################
#
#         # Get current active attendance session
#         attendance = self.env['hr.attendance'].search([
#             ('employee_id', '=', employee_id),
#             ('check_out', '=', False)
#         ], limit=1)
#
#         vals = {
#             'employee_id': employee_id,
#             'attendance_id': attendance.id if attendance else False,
#             'latitude': latitude,
#             'longitude': longitude,
#             'tracking_type': tracking_type,
#             'timestamp': fields.Datetime.now(),
#             'address': address
#         }
#         return self.create(vals)
#
#
# # Extend existing models to integrate tracking
# class HrAttendance(models.Model):
#     _inherit = 'hr.attendance'
#
#     @api.model
#     def create(self, vals):
#         """Override create to add route tracking"""
#         attendance = super().create(vals)
#         # Create route tracking point for check-in
#         if ('check_in' in vals and vals.get('in_latitude') and vals.get('in_longitude')
#                 #######################################################################################################
#                 and attendance.employee_id.user_id and attendance.employee_id.user_id.enable_gps_tracking):
#             #######################################################################################################
#             self.env['gps.tracking'].create_route_point(
#                 employee_id=attendance.employee_id.id,
#                 latitude=vals['in_latitude'],
#                 longitude=vals['in_longitude'],
#                 tracking_type='check_in',
#                 address=attendance.check_in_address if attendance.check_in_address else ""
#             )
#
#         return attendance
#
#     def write(self, vals):
#         """Override write to handle check-out tracking"""
#         result = super().write(vals)
#
#         # Create route tracking point for check-out
#         if 'check_out' in vals and vals.get('out_latitude') and vals.get('out_longitude'):
#             for attendance in self:
#                 ##########################################################################################
#                 if (attendance.employee_id.user_id and
#                         attendance.employee_id.user_id.enable_gps_tracking):
#                     ###########################################################################################
#                     self.env['gps.tracking'].create_route_point(
#                         employee_id=attendance.employee_id.id,
#                         latitude=vals['out_latitude'],
#                         longitude=vals['out_longitude'],
#                         tracking_type='check_out',
#                         address=attendance.check_out_address if attendance.check_out_address else ""
#                     )
#
#         return result
#
#
# #################################################################################################
# class ResUsers(models.Model):
#     _inherit = 'res.users'
#
#     enable_gps_tracking = fields.Boolean(
#         string='Enable GPS Tracking',
#         default=False,
#         help='Enable GPS tracking for this user. When disabled, the user will not be able to send GPS data or view tracking information.'
#     )
#
#
# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'
#
#     time_interval = fields.Integer(string="Time Interval(ms)", default=5000,
#                                    help='Time between gps auto fetch in milliseconds.')
#
#     def set_values(self):
#         super().set_values()
#         self.env['ir.config_parameter'].sudo().set_param(
#             'field_service_tracking.time_interval', self.time_interval
#         )
#
#     @api.model
#     def get_values(self):
#         res = super().get_values()
#         res.update(
#             time_interval=int(
#                 self.env['ir.config_parameter'].sudo().get_param(
#                     'field_service_tracking.time_interval', default=5000
#                 )
#             )
#         )
#         return res
#
# #################################################################################################
