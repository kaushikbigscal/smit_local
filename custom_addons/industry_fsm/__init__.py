# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import controllers
from . import wizard
from . import populate
from odoo import _, Command


# def create_field_service_project(env):
#     fsm_project = env.ref('industry_fsm.fsm_project', raise_if_not_found=False)
#     project_vals = env['res.company'].search(
#         [('id', '!=', fsm_project.company_id.id)])._get_field_service_project_values()
#     env['project.project'].create(project_vals)

def create_field_service_project(env):
    fsm_project = env.ref('industry_fsm.fsm_project', raise_if_not_found=False)
    if fsm_project is None:
        # Handle the case where fsm_project is not found
        return  # or raise an exception if necessary

    project_vals = env['res.company'].search(
        [('id', '!=', fsm_project.company_id.id)])._get_field_service_project_values()
    env['project.project'].create(project_vals)
