


def post_init_hook(env):
    """Put the date with 00:00:00 as the date_time for the line."""
    env.cr.execute(
        """UPDATE account_analytic_line
        SET date_time = to_timestamp(date || ' 00:00:00',
                                     'YYYY/MM/DD HH24:MI:SS')
        WHERE date(date_time) != date
        """
    )
