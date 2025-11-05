def is_fsm_installed(env):
    """Check if the industry_fsm module is installed."""
    return env['ir.module.module'].sudo().search_count([
        ('name', '=', 'industry_fsm'),
        ('state', '=', 'installed')
    ]) > 0
