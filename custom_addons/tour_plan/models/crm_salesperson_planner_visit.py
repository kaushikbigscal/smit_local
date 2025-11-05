
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmSalespersonPlannerVisitTimesheet(models.Model):
    _name = "crm.salesperson.planner.visit.timesheet"
    _description = "Timesheet Entry"


    visit_id = fields.Many2one(
        comodel_name="crm.salesperson.planner.visit",
        string="Visit",
        required=True,
        ondelete='cascade',
    )
    start_time = fields.Datetime(string="Start Time", required=True)
    end_time = fields.Datetime(string="End Time")
    total_working_time = fields.Float(string="Total Working Time", compute="_compute_total_working_time", store=True)

    @api.depends('start_time', 'end_time')
    def _compute_total_working_time(self):
        for record in self:
            if record.start_time and record.end_time:
                record.total_working_time = (record.end_time - record.start_time).total_seconds() / 3600.0
            else:
                record.total_working_time = 0.0


class StartWorkWizard(models.TransientModel):
    _name = 'start.work.wizard'
    _description = 'Start Work Wizard'

    visit_id = fields.Many2one('crm.salesperson.planner.visit', string="Visit", required=True)

    def action_start_work(self):

        user_id = self.visit_id.user_id

        ongoing_visit = self.env['crm.salesperson.planner.visit'].search([
            ('user_id', '=', user_id.id),
            ('is_work_started', '=', True),
            ('id', '!=', self.id)
        ], limit=1)

        if ongoing_visit:
            raise ValidationError(_(
                "The salesperson is already working on another visit: '%s'. Please stop work on that visit first."
            ) % ongoing_visit.name)



        timesheet = self.env['crm.salesperson.planner.visit.timesheet'].create({
            'visit_id': self.visit_id.id,
            'start_time': fields.Datetime.now(),
        })

        self.visit_id.timesheet_ids = [(4, timesheet.id)]

        self.visit_id.show_time_control = 'stop'
        self.visit_id.is_work_started = True

        return {'type': 'ir.actions.act_window_close'}




class EndWorkWizard(models.TransientModel):
    _name = 'end.work.wizard'
    _description = 'End Work Wizard'

    visit_id = fields.Many2one('crm.salesperson.planner.visit', string="Visit", required=True)

    def action_end_work(self):

        is_work_started = self.visit_id.is_work_started
        if not is_work_started:
            raise ValidationError(_("Work is not started yet for this visit."))

        minimum_duration = float(self.env['ir.config_parameter'].sudo().get_param('tour_plan.Minimum_Duration_end_work',default=0.0))
        print(minimum_duration)
        if self.visit_id.timesheet_ids:

            last_timesheet = self.visit_id.timesheet_ids[-1]
            time_diff = (fields.Datetime.now() - last_timesheet.start_time).total_seconds() / 60.0  # in minutes

            if time_diff < minimum_duration:
                raise ValidationError(
                    _("You cannot stop work before the minimum duration of {} minutes.".format(minimum_duration))
                )
            last_timesheet.end_time = fields.Datetime.now()
        else:
            raise ValidationError(_("No active timesheet found to end work."))

        self.visit_id.show_time_control = 'start'
        self.visit_id.is_work_started = False


        return {'type': 'ir.actions.act_window_close'}  # Close the wizard





class CrmSalespersonPlannerVisit(models.Model):
    _name = "crm.salesperson.planner.visit"
    _description = "Salesperson Planner Visit"
    _order = "date desc,sequence"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _systray_view = 'activity'

    name = fields.Char(
        string="Visit Number",
        required=True,
        default="Draft",
        copy=False,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        required=True,
    )
    partner_phone = fields.Char(string="Phone", related="partner_id.phone")
    partner_mobile = fields.Char(string="Mobile", related="partner_id.mobile")
    date_start = fields.Datetime(string='Start Date')
    date = fields.Datetime(string='Expiration Date', index=True, tracking=True,
                       help="Date on which this project ends. The timeframe defined on the project is taken into account when viewing its planning.")
    sequence = fields.Integer(
        help="Used to order Visits in the different views",
        default=20,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Salesperson",
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
        domain=lambda self: [
            ("groups_id", "in", self.env.ref("sales_team.group_sale_salesman").id)
        ],
    )


    description = fields.Html()
    state = fields.Selection(
        string="Status",
        required=True,
        copy=False,
        tracking=True,
        selection=[
            ("draft", "Draft"),
            ("confirm", "Validated"),
            ("done", "Visited"),
            ("cancel", "Cancelled"),
            ("incident", "Incident"),
        ],
        default="draft",
    )
    close_reason_id = fields.Many2one(
        comodel_name="crm.salesperson.planner.visit.close.reason", string="Close Reason"
    )
    close_reason_image = fields.Image(max_width=1024, max_height=1024, attachment=True)
    close_reason_notes = fields.Text()
    visit_template_id = fields.Many2one(
        comodel_name="crm.salesperson.planner.visit.template", string="Visit Template"
    )
    calendar_event_id = fields.Many2one(
        comodel_name="calendar.event", string="Calendar Event"
    )

    _sql_constraints = [
        (
            "crm_salesperson_planner_visit_name",
            "UNIQUE (name)",
            "The visit number must be unique!",
        ),
    ]

    show_time_control = fields.Selection(
        selection=[
            ('start', 'Start Work'),
            ('stop', 'Stop Work'),
        ],
        string="Work Control",
        default='start',
    )

    timesheet_ids = fields.One2many(
        comodel_name="crm.salesperson.planner.visit.timesheet",
        inverse_name="visit_id",
        string="Timesheets",
    )
    is_work_started = fields.Boolean(string="Work Started", default=False)
    visit_objective = fields.Many2many('visit.objective', string='Visit Objective')


    @api.depends('start_time', 'end_time')
    def _compute_total_working_time(self):
        for record in self:
            if record.start_time and record.end_time:
                record.total_working_time = (record.end_time - record.start_time).total_seconds() / 3600.0
            else:
                record.total_working_time = 0.0



    def button_start_work(self):

        if self.state != 'confirm':
            raise ValidationError(_("You can only start work when the visit is Validate."))

        return {
            'name': 'Start Work',
            'type': 'ir.actions.act_window',
            'res_model': 'start.work.wizard',  # This should match the model name defined above
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }


    def button_end_work(self):


        return {

            'name': 'Stop Work',
            'type': 'ir.actions.act_window',
            'res_model': 'end.work.wizard',  # This should match the model name defined above
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "salesperson.planner.visit"
                )
            if vals.get('user_id') and vals.get('date_start') and vals.get('date'):
                salesperson = vals['user_id']
                start_time = fields.Datetime.from_string(vals['date_start'])
                end_time = fields.Datetime.from_string(vals['date'])

                overlapping_visits = self.search([
                    ('user_id', '=', salesperson),
                    ('state', 'not in', ['cancel', 'done']),
                    '|',
                    ('date_start', '<', end_time),
                    ('date', '>', start_time),
                ])

                for visit in overlapping_visits:

                    visit_start = visit.date_start
                    visit_end = visit.date
                    if (start_time < visit_end and end_time > visit_start):
                        raise ValidationError(
                            _("The salesperson already has a visit scheduled that overlaps with the proposed time.")
                        )
        visit_records = super().create(vals_list)
        for visit in visit_records:
            visit.message_subscribe([visit.partner_id.id,self.env.user.partner_id.id])

        return visit_records

    def action_draft(self):
        if self.state not in ["cancel", "incident", "done"]:
            raise ValidationError(
                _("The visit must be in cancelled, incident or visited state")
            )
        if self.calendar_event_id:
            self.calendar_event_id.with_context(bypass_cancel_visit=True).unlink()
        self.write({"state": "draft"})

    def action_confirm(self):
        if self.filtered(lambda a: not a.state == "draft"):
            raise ValidationError(_("The visit must be in draft state"))
        events = self.create_calendar_event()
        if events:
            self.browse(events.mapped("res_id")).write({"state": "confirm"})

    def action_done(self):
        if not self.state == "confirm":
            raise ValidationError(_("The visit must be in confirmed state"))


        incomplete_timesheets = self.timesheet_ids.filtered(lambda t: not t.end_time)
        if incomplete_timesheets:
            raise ValidationError(
                _("You must stop the work before marking the visit as done"))


        complete_timesheets = self.timesheet_ids.filtered(lambda t: t.start_time and t.end_time)
        if not complete_timesheets:
            raise ValidationError(
                _("At least one entry with both start and end times is required to mark the visit as done."))

        self.write({"state": "done"})

    def action_cancel(self, reason_id, image=None, notes=None):
        if self.state not in ["draft", "confirm"]:
            raise ValidationError(_("The visit must be in draft or validated state"))
        if self.is_work_started:
            self.show_time_control = 'start'
            self.is_work_started = False

            if self.timesheet_ids:
                last_timesheet = self.timesheet_ids[-1]
                last_timesheet.end_time = fields.Datetime.now()
            else:
                raise ValidationError(_("No active timesheet found to end work."))

        if self.calendar_event_id:
            self.calendar_event_id.with_context(bypass_cancel_visit=True).unlink()
        self.write(
            {
                "state": "cancel",
                "close_reason_id": reason_id.id,
                "close_reason_image": image,
                "close_reason_notes": notes,
            }
        )

    def _prepare_calendar_event_vals(self):
        return {
            "name": self.name,
            "partner_ids": [(6, 0, [self.partner_id.id, self.user_id.partner_id.id])],
            "user_id": self.user_id.id,
            "start_date": self.date_start,
            "stop_date": self.date,
            "start": self.date_start,
            "stop": self.date,
            "allday": False,
            "res_model": self._name,
            "res_model_id": self.env.ref(
                "tour_plan.model_crm_salesperson_planner_visit"
            ).id,
            "res_id": self.id,
        }

    def create_calendar_event(self):
        events = self.env["calendar.event"]
        for item in self:
            event = self.env["calendar.event"].create(
                item._prepare_calendar_event_vals()
            )
            if event:
                event.activity_ids.unlink()
                item.calendar_event_id = event
            events += event
        return events

    def action_incident(self, reason_id, image=None, notes=None):
        if self.state not in ["draft", "confirm"]:
            raise ValidationError(_("The visit must be in draft or validated state"))
        if self.is_work_started:
            self.show_time_control = 'start'
            self.is_work_started = False

            if self.timesheet_ids:
                last_timesheet = self.timesheet_ids[-1]
                last_timesheet.end_time = fields.Datetime.now()
            else:
                raise ValidationError(_("No active timesheet found to end work."))

        self.write(
            {
                "state": "incident",
                "close_reason_id": reason_id.id,
                "close_reason_image": image,
                "close_reason_notes": notes,
            }
        )

    def unlink(self):
        if any(sel.state not in ["draft", "cancel"] for sel in self):
            raise ValidationError(_("Visits must be in cancelled state"))
        return super().unlink()

    def write(self, values):
        ret_val = super().write(values)
        if (values.get("date") or values.get("user_id")) and not self.env.context.get(
                "bypass_update_event"
        ):
            new_vals = {}
            for item in self.filtered(lambda a: a.calendar_event_id):
                if values.get("date"):
                    new_vals["start"] = values.get("date_start")
                    new_vals["stop"] = values.get("date")
                if values.get("user_id"):
                    new_vals["user_id"] = values.get("user_id")
                item.calendar_event_id.write(new_vals)
        return ret_val
