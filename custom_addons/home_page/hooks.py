from odoo import api, SUPERUSER_ID

def post_init_calendar_sync(cr, registry):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        # backfill all existing tasks and leads
        env['project.task'].search([])._sync_to_calendar()
        env['crm.lead'].search([])._sync_to_calendar()
    # no return needed
