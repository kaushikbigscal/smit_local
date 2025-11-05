# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint

from odoo import api, fields, models, SUPERUSER_ID
from odoo.osv import expression


class VisitObjectiveTag(models.Model):
    _name = "visit.objective"
    _description = "Visit Objective"
    _order = "name"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=_get_default_color,
        help="Transparent tags are not visible in the kanban view of your projects and tasks.")

    @api.model
    def name_create(self, name):
        existing_objective = self.search([('name', '=ilike', name.strip())], limit=1)
        if existing_objective:
            return existing_objective.id, existing_objective.display_name
        return super().name_create(name)
