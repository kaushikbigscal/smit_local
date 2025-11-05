from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

def _send_customer_notification(self, partner, subject, message, url=''):
    if not partner:
        return

    portal_notification_installed = self.env['ir.module.module'].sudo().search_count([
        ('name', '=', 'notification'),
        ('state', '=', 'installed')
    ]) > 0

    if portal_notification_installed:
        success = self.env['mail.partner.device'].send_webpush_to_partner(
            partner=partner,
            title=subject,
            body=message,
            url=url
        )
        if success:
            _logger.info("Webpush notification sent successfully")
        else:
            _logger.warning("Webpush notification failed to send")

    self.env['portal.notification'].sudo().create_for_partner(
        partner=partner,
        title=subject,
        message=message,
        url=url or "/my/home",
        res_model=self._name,
        res_id=self.id
    )


def patch_customer_notifications_on_model(env):
    models_to_patch = {
        'customer.product.mapping': {
            'required_module': 'industry_fsm',
            'customer_field': 'customer_id',
            'get_subject': 'Product Mapping Update',
            'get_message': lambda rec, kwargs=None: (
                (f"New message received in {rec.product_id.name or 'Asset'}, " + kwargs.get(
                    'body') if kwargs and 'body' in kwargs else "No message provided.")
            ),
            'get_url': lambda rec: f"/my/asset/{rec.id}",
            'dynamic_flags': lambda rec: {'use_message_post': True, 'use_write': False},
        },
        'amc.contract': {
            'required_module': 'inventory_custom_tracking_installation_delivery',
            'customer_field': 'partner_id',
            'get_subject': 'Contract Update',
            'get_message': lambda rec, kwargs=None: (
                (f"New message received in contract {rec.name or 'Contract'}, " + kwargs.get(
                    'body') if kwargs and 'body' in kwargs else "No message provided.")
            ),
            'get_url': lambda rec: f"/my/contract/form/{rec.id}",
            'dynamic_flags': lambda rec: {'use_message_post': True, 'use_write': False},
        },
        'sale.order': {
            'required_module': 'sale',
            'customer_field': 'partner_id',
            'trigger_field': 'state',
            'trigger_value': ['sent', 'sale'],
            'get_subject': lambda rec: (
                "Quotation Sent" if rec.state == 'sent' else
                "Sale Order Sent" if rec.state == 'sale' else
                "Chatter Message"
            ),
            'get_message': lambda rec, kwargs=None: (
                "Quotation is created and ready for your review."
                if rec.state == 'sent' else
                "Sale Order is created and ready for your review."
                if rec.state == 'sale' else
                (kwargs.get('body') if kwargs and 'body' in kwargs else "No message provided.")
            ),
            'get_url': lambda rec: f"/my/orders/{rec.id}?access_token={rec.sudo()._portal_ensure_token()}",
            'dynamic_flags': lambda rec, vals=None: {
                # If vals is passed (write/update), check the state in vals
                'use_message_post': True,
                'use_write': False if not vals else vals.get('state') == 'sale',
            },
        },

        'account.move': {
            'required_module': 'sale',
            'customer_field': 'partner_id',
            'trigger_field': 'state',
            'trigger_value': 'posted',
            'get_subject': 'Invoice Created',
            'get_message': lambda rec, kwargs=None: (
                "New invoice is shared with you."
                if rec.state == 'posted' else
                ("Invoice Update, " + kwargs.get('body') if kwargs and 'body' in kwargs else "No message provided.")
            ),
            'get_url': lambda rec: f"/my/invoices/{rec.id}?access_token={rec.sudo()._portal_ensure_token()}",
            'dynamic_flags': lambda rec, vals=None: {'use_message_post': True, 'use_write': True},
            'extra_condition': lambda rec: rec.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'],
        },
    }

    for model_name, config in models_to_patch.items():
        if model_name not in env:
            continue
        ModelClass = env.registry[model_name]
        required_module = config.get('required_module')
        module_installed = not required_module or env['ir.module.module'].sudo().search_count([
            ('name', '=', required_module),
            ('state', '=', 'installed')
        ]) > 0
        if not module_installed:
            continue

        if not hasattr(ModelClass, '_send_customer_notification'):
            ModelClass._send_customer_notification = _send_customer_notification

        # ---------- PATCH message_post ----------
        original_post = ModelClass.message_post

        def make_patch_message_post(original_method, config):
            def patched_message_post(self, **kwargs):
                message = original_method(self, **kwargs)
                if kwargs.get('message_type') != 'comment':
                    return message

                current_user = self.env.user
                is_portal = current_user.has_group('base.group_portal')

                for record in self:
                    flags = config.get('dynamic_flags', lambda r: {
                        'use_message_post': config.get('use_message_post', False),
                        'use_write': config.get('use_write', False),
                    })
                    # flags = config.get('dynamic_flags', lambda r, v=None: {
                    #     'use_message_post': config.get('use_message_post', False),
                    #     'use_write': config.get('use_write', False),
                    # })
                    # flags = flags(record, vals) if callable(flags) else flags

                    flags = flags(record) if callable(flags) else flags

                    if not flags.get('use_message_post'):
                        continue

                    customer = getattr(record, config['customer_field'], False)
                    extra_condition = config.get('extra_condition')
                    if extra_condition and not extra_condition(record):
                        continue

                    try:
                        subj = config['get_subject'](record) if callable(config['get_subject']) else config['get_subject']
                        # msg = config['get_message'](record) if callable(config['get_message']) else config['get_message']
                        body = kwargs.get('body') or kwargs.get('message') or "No message provided."
                        msg = config['get_message'](record, {'body': body}) if callable(config['get_message']) else \
                        config['get_message']
                        url = config['get_url'](record) if 'get_url' in config else '/my/ticket'

                        if is_portal:
                            users = getattr(record, 'user_ids', []) or ([record.user_id] if hasattr(record, 'user_id') else [])
                            for u in users:
                                if u and u.partner_id:
                                    record._send_customer_notification(u.partner_id, subj, msg, url)
                        else:
                            if customer and customer.user_ids:
                                for u in customer.user_ids:
                                    if u.has_group('base.group_portal'):
                                        record._send_customer_notification(customer, subj, msg, url)
                    except Exception:
                        _logger.exception(f"WebPush error in {model_name}")

                return message
            return patched_message_post

        ModelClass.message_post = make_patch_message_post(original_post, config)

        # ---------- PATCH write ----------
        original_write = ModelClass.write

        def make_patch_write(original_method, config):
            def patched_write(self, vals):
                _logger.info("PATCH WRITE: Starting write patch for model %s with vals: %s", self._name, vals)

                result = original_method(self, vals)
                _logger.info("PATCH WRITE: Original write completed, result=%s", result)

                trigger_field = config.get('trigger_field')
                trigger_value = config.get('trigger_value')

                notify_records = self.filtered(
                    lambda r: trigger_field in vals and (
                            (isinstance(trigger_value, list) and vals[trigger_field] in trigger_value) or
                            (vals[trigger_field] == trigger_value)
                    )
                )

                _logger.info("PATCH WRITE: Records matching trigger (%s=%s): %s",
                             trigger_field, trigger_value, notify_records.ids)

                for record in notify_records:
                    _logger.info("PATCH WRITE: Processing record %s (%s)", record.id, record._name)

                    # flags = config.get('dynamic_flags', lambda r: {
                    #     'use_message_post': config.get('use_message_post', False),
                    #     'use_write': config.get('use_write', False),
                    # })
                    # flags = flags(record) if callable(flags) else flags
                    flags = config.get('dynamic_flags', lambda r, v=None: {
                        'use_message_post': config.get('use_message_post', False),
                        'use_write': config.get('use_write', False),
                    })
                    flags = flags(record, vals) if callable(flags) else flags
                    _logger.info("PATCH WRITE: Flags for record %s: %s", record.id, flags)

                    if not flags.get('use_write'):
                        _logger.info("PATCH WRITE: Skipping record %s because use_write=False", record.id)
                        continue

                    customer = getattr(record, config['customer_field'], False)
                    _logger.info("PATCH WRITE: Customer for record %s: %s", record.id,
                                 customer.id if customer else None)

                    if not customer or not customer.user_ids:
                        _logger.info("PATCH WRITE: Skipping record %s because customer has no linked users", record.id)
                        continue

                    portal_users = [u for u in customer.user_ids if u.has_group('base.group_portal')]
                    if not portal_users:
                        _logger.info("PATCH WRITE: Skipping record %s because no portal users found for customer %s",
                                     record.id, customer.id)
                        continue

                    extra_condition = config.get('extra_condition')
                    if extra_condition and not extra_condition(record):
                        _logger.info("PATCH WRITE: Skipping record %s due to extra_condition failing", record.id)
                        continue

                    try:
                        subj = config['get_subject'](record) if callable(config['get_subject']) else config[
                            'get_subject']
                        msg = config['get_message'](record) if callable(config['get_message']) else config[
                            'get_message']
                        url = config['get_url'](record) if 'get_url' in config else '/my/ticket'

                        _logger.info(
                            "PATCH WRITE: Sending notification -> Model: %s, Record ID: %s, Customer: %s, Users: %s, URL: %s, Subject: %s",
                            record._name, record.id, customer.id, [u.id for u in portal_users], url, subj
                        )

                        for user in portal_users:
                            record._send_customer_notification(user.partner_id, subj, msg, url)
                            _logger.info(
                                "PATCH WRITE: Notification sent to portal user %s (partner_id=%s) for record %s",
                                user.id, user.partner_id.id, record.id
                            )

                    except Exception as e:
                        _logger.exception(
                            "PATCH WRITE: WebPush error in %s for record %s: %s",
                            record._name, record.id, e
                        )

                _logger.info("PATCH WRITE: Finished processing notifications for model %s", self._name)
                return result

            return patched_write

        ModelClass.write = make_patch_write(original_write, config)

        # ---------- PATCH unlink ----------
        original_unlink = ModelClass.unlink

        def make_patch_unlink(original_method):
            def patched_unlink(self):
                portal_notification_installed = self.env['ir.module.module'].sudo().search_count([
                    ('name', '=', 'notification'),
                    ('state', '=', 'installed')
                ]) > 0

                for rec in self:
                    if portal_notification_installed:
                        notifications = self.env['portal.notification'].sudo().search([
                            ('res_model', '=', rec._name),
                            ('res_id', '=', rec.id)
                        ])
                        if notifications:
                            notifications.unlink()
                    return original_method(self)
            return patched_unlink

        ModelClass.unlink = make_patch_unlink(original_unlink)
