from odoo import models, fields, api, tools
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ServiceChargeReport(models.Model):
    _name = 'service.charge.report'
    _description = 'Service Charge Report'
    _auto = False

    _log_access = False  

    # Prevent create, write, unlink
    def create(self, vals):
        raise UserError("This is a report model and cannot be modified.")

    def write(self, vals):
        raise UserError("This is a report model and cannot be modified.")

    def unlink(self):
        raise UserError("This is a report model and cannot be deleted.")
    # ==============================
    # Related fields from task
    # ==============================
    task_id = fields.Many2one('project.task', string='Task', required=True, readonly=True)
    name = fields.Char(string='Call Name', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    call_allocation = fields.Char(string='Call Allocation', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    call_type = fields.Many2one(comodel_name='call.type', string="Call Type", readonly=True)
    paid_amount = fields.Float(string='Paid Amount', readonly=True)
    remaining_amount = fields.Float(string='Remaining Amount', readonly=True)
    payment_status = fields.Char(string='Payment Status', readonly=True)
    user_ids = fields.Many2many('res.users', string='Assignees', related='task_id.user_ids', readonly=True)

    # ==============================
    # View-specific computed columns
    # ==============================
    total_charge = fields.Float(string='Total Charge', readonly=True)
    service_charge_type_name = fields.Char(string='Service Charge Type', readonly=True)

    primary_user_id = fields.Many2one('res.users', string='Primary Assignee', readonly=True)

    # ==============================
    # View creation logic
    # ==============================
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    pt.id AS id,
                    pt.id AS task_id,
                    pt.name AS name,
                    pt.department_id AS department_id,
                    pt.call_allocation AS call_allocation,
                    pt.partner_id AS partner_id,
                    ct.id AS call_type,
                    pt.paid_amount AS paid_amount,
                    pt.remaining_amount AS remaining_amount,
                    pt.total_charge AS total_charge,
                    pt.payment_status AS payment_status,
                    (
                        SELECT rel.user_id
                        FROM project_task_user_rel rel
                        WHERE rel.task_id = pt.id
                        ORDER BY rel.user_id
                        LIMIT 1
                    ) AS primary_user_id,
                    (
                        SELECT STRING_AGG(sct.service_charge_type, ', ' ORDER BY s.id)
                        FROM service_charge s
                        JOIN service_charge_type sct ON s.service_charge_type = sct.id
                        WHERE s.task_id = pt.id
                    ) AS service_charge_type_name
                FROM project_task pt
                LEFT JOIN call_type ct ON ct.id = pt.call_type
            )
        """)
         
    # ==============================
    # Action to open calls form
    # ==============================
    def action_open_task(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Calls',
            'res_model': 'project.task',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
