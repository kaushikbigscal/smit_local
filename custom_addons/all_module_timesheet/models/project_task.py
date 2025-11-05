from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    can_start_timer = fields.Boolean(
        string='Can Start Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )
    can_stop_timer = fields.Boolean(
        string='Can Stop Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )

    @api.depends('timesheet_ids.is_timer_running', 'timesheet_ids.user_id')
    def _compute_timer_button_visibility(self):
        for task in self:
            user_timer = task.timesheet_ids.filtered(
                lambda t: t.user_id.id == task.env.user.id and t.task_id.id == task.id)
            running = user_timer.filtered(lambda t: t.is_timer_running)

            # Default: all False
            task.can_start_timer = False
            task.can_stop_timer = False

            if not running:
                task.can_start_timer = True
            else:
                task.can_stop_timer = True

    def action_start_task_timer(self):
        """Start a timesheet timer for this task."""
        self.ensure_one()

        if self.state == '04_waiting_normal':
            raise ValidationError("You can not start timer in Blocked task.")

        # Restriction: Task must have at least one assignee
        if not self.user_ids:
            raise ValidationError("This task has no assignees! Please add assignees to start work.")

        # Restriction: Only assigned users can start the timer
        if self.env.user not in self.user_ids:
            raise ValidationError("Only assigned users can start the timer.")

        # Find any running timer for the current user
        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True)
        ], limit=1)

        if running_timer:
            raise ValidationError(f"You already have a running timer: {running_timer.name}")

        # You should handle default category ID properly or pass it from the form
        default_category = self.env['custom.timesheet.category'].search([('code', '=', 'PROJECT')], limit=1)
        if not default_category:
            raise ValidationError("Please define at least one timesheet category.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)
        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        timesheet = self.env['account.analytic.line'].create({
            'name': f'Task: {self.name}',
            'user_id': self.env.user.id,
            'task_id': self.id,
            'project_id': self.project_id.id,
            'category_id': default_category.id,
            'source_model': 'project.task',
            'source_record_id': self.id,
            'start_latitude': latitude,
            'start_longitude': longitude,
            'start_address': address,
        })

        # --- Create GPS Tracking Point (CALL START) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_start',
                address=address,
                source_model='project.task',
                source_record_id=self.id,
            )

        return timesheet.action_start_timer()

    def action_stop_task_timer(self):
        """Stop the currently running timer for this task."""
        self.ensure_one()

        # Restriction: Task must have at least one assignee
        if not self.user_ids:
            raise ValidationError("This task has no assignees! Please add assignees to stop work.")

        # Restriction: Only assigned users can start the timer
        if self.env.user not in self.user_ids:
            raise ValidationError("Only assigned users can stop the timer.")

        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('task_id', '=', self.id),
        ], limit=1)

        if not running_timer:
            raise ValidationError("No running timer found for this task.")

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)
        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        running_timer.write({
            'end_latitude': latitude,
            'end_longitude': longitude,
            'end_address': address,
        })

        # --- Create GPS Tracking Point (CALL END) ---
        if 'gps.tracking' in self.env and self.env.user.employee_id and self.env.user.enable_gps_tracking:
            self.env['gps.tracking'].create_route_point(
                employee_id=self.env.user.employee_id.id,
                latitude=latitude,
                longitude=longitude,
                tracking_type='call_end',
                address=address,
                source_model='project.task',
                source_record_id=self.id,
            )

        return running_timer.action_stop_timer()

    # auto timesheet entry for task
    def write(self, vals):
        # Check if auto timesheet setting is enabled
        auto_entry_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'all_module_timesheet.auto_timesheet_entry'
        ) in ['1', True, 'true', 'True']

        # Store old states for state transition tracking
        task_state = {task.id: task.state for task in self}

        # Perform actual write operation first
        result = super().write(vals)

        for task in self:
            if task.project_id:
                # ✅ Auto start/stop timer logic
                if auto_entry_enabled and not task.is_fsm and 'state' in vals:
                    # Prevent multi-task simultaneous start
                    if vals.get('state') == '01_in_progress' and len(self) > 1:
                        raise ValidationError("You can only start timesheet for one task at a time.")
                    if vals.get('state') in ('1_done', '1_canceled') and len(self) > 1:
                        raise ValidationError("You can only stop timesheet for one task at a time.")

                    old_state = task_state.get(task.id)
                    new_state = task.state  # now it's updated
                    if old_state != new_state:
                        if new_state == '01_in_progress':
                            task.action_start_task_timer()
                        elif new_state in ('1_done', '1_canceled'):
                            task.action_stop_task_timer()

                # ✅ Update timesheet names if task name has changed
                if 'name' in vals:
                    new_name = f"Call: {task.name}" if task.is_fsm else f"Task: {task.name}"
                    self.env['account.analytic.line'].search([('task_id', '=', task.id)]).write({
                        'name': new_name
                    })

        return result
