from odoo import fields, models


class ReportProjectTaskUser(models.Model):
    _name = 'report.project.task.user.fsm'
    _inherit = 'report.project.task.user'
    _description = "FSM Tasks Analysis"
    _auto = False

    pending_call_count = fields.Integer(string="Pending Calls", readonly=True)
    completed_call_count = fields.Integer(string="Completed Calls", readonly=True)

    # def _select(self):
    #     project_id = self.env['project.project'].search([('is_fsm', '=', True)], limit=1).id
    # 
    #     in_progress_stage_id = self.env['project.task.type'].search([
    #         ('name', '=', 'Pending'),
    #         ('project_ids', 'in', [project_id])
    #     ], limit=1).id
    # 
    #     done_stage_id = self.env['project.task.type'].search([
    #         ('name', '=', 'Done'),
    #         ('project_ids', 'in', [project_id])
    #     ], limit=1).id
    # 
    #     return super()._select() + f"""
    # 
    #         , COUNT(CASE WHEN t.stage_id = {in_progress_stage_id} THEN 1 END) AS pending_call_count
    #         , COUNT(CASE WHEN t.stage_id = {done_stage_id} THEN 1 END) AS completed_call_count
    # 
    # 
    # 
    #     """
    # 
    # def _from(self):
    #     return super()._from() + """
    #             INNER JOIN project_project pp
    #                 ON pp.id = t.project_id
    #                 AND pp.is_fsm = 'true'
    #             LEFT JOIN res_partner rp
    #                 ON rp.id = t.partner_id
    #             LEFT JOIN account_analytic_line ts ON ts.task_id = t.id
    # 
    #     """
