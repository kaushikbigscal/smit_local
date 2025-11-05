# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizards


def _pre_init_update_rule(env):
    env.cr.execute("""UPDATE ir_model_data SET noupdate=False WHERE model = 'hr.salary.rule'""")
