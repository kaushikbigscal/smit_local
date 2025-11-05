from datetime import timedelta
from odoo import models, fields, api,  _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    notify_customer = fields.Boolean("Notify Customers" , default=False)
    notification_type = fields.Selection([
        ('whatsapp', 'Whatsapp'),
        ('email', 'Email')], string="Notification Type")

    @api.onchange('notify_customer')
    def _onchange_notify_customer(self):
        if self.notify_customer:
            module = self.env['ir.module.module'].sudo().search([('name', '=', 'hr_holidays')], limit=1)
            if module and module.state != 'installed':
                module.button_immediate_install()
            elif not module:
                raise UserError(_("HR Holidays module is not available in the system."))

    @api.onchange('notify_customer')
    def _onchange_notify_customer_clear(self):
        if not self.notify_customer:
            self.notification_type = False


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    frequency = fields.Selection([
        ('once', 'Only Once'),
        ('daily', 'Daily during closure'),
        ('both', 'Both')], string="Frequency", default='once', required=True)

    customer_selection = fields.Selection([
        ('active', 'Active Customers'),
        ('specific', 'Specific Group Customer')], string="Customer Selection", default='active', required=True)

    customer_id = fields.Many2one('res.partner', string="Customer")
    notification_type = fields.Selection([
        ('whatsapp', 'Whatsapp'),
        ('email', 'Email')], string="Notification Type")

    category_id = fields.Many2many('res.partner.category', string="Tags")

    @api.model
    def send_holiday_notifications(self):
        today = fields.Date.today()
        print("Today's date:", today)

        company = self.env.company
        if not company.notify_customer:
            print("Notifications disabled. Exiting.")
            return

        # get email template
        template = self.env['mail.template'].search(
            [('name', '=', 'Holiday Notification')], limit=1)
        if not template:
            print("No template found. Exiting.")
            return

        # prefetch model + whatsapp template
        model_id = self.env['ir.model'].search([('model', '=', 'hr.leave')], limit=1)
        whatsapp_template = self.env['template.whatsapp'].search([('model_id', '=', model_id.id)], limit=1)
        if company.notification_type == 'whatsapp' and not whatsapp_template:
            print("No WhatsApp template found. Exiting.")
            return

        leaves = self.search([])
        for leave in leaves:
            start_date = leave.date_from.date() if leave.date_from else None
            end_date = leave.date_to.date() if leave.date_to else start_date
            holiday_reason = leave.name or "holidays"

            if start_date == end_date:
                holiday_period = f"on {start_date.strftime('%d %b, %Y')}"
            else:
                holiday_period = f"from {start_date.strftime('%d %b, %Y')} to {end_date.strftime('%d %b, %Y')}"

            print(f"\nProcessing leave {leave.name or leave.id}, Start Date: {start_date}, End Date: {end_date}")
            next_working_date = (end_date + timedelta(days=1)).strftime("%d %b, %Y")

            # check frequency
            should_send = False
            send_reason = ""
            if leave.frequency == 'once':
                send_date = start_date - timedelta(days=1)
                if send_date == today:
                    should_send = True
                    send_reason = "Once (day before)"
            elif leave.frequency == 'daily':
                if start_date <= today <= end_date:
                    should_send = True
                    send_reason = "Daily (during holiday)"
            elif leave.frequency == 'both':
                send_date = start_date - timedelta(days=1)
                if send_date == today:
                    should_send = True
                    send_reason = "Both (day before)"
                elif start_date <= today <= end_date:
                    should_send = True
                    send_reason = "Both (during holiday)"

            if not should_send:
                print(f"  Skipping - Today {today} doesn't match frequency {leave.frequency}")
                continue

            print(f"  Sending notification - Reason: {send_reason}")

            #  filter customers based on selection
            if leave.customer_selection == 'active':
                if company.notification_type == 'email':
                    customers_to_notify = self.env['res.partner'].search([
                        ('active', '=', True),
                        ('email', '!=', False),
                        ('parent_id', '=', False)])
                else:
                    customers_to_notify = self.env['res.partner'].search([
                        ('active', '=', True),
                        ('parent_id', '=', False),
                        '|', ('mobile', '!=', False), ('phone', '!=', False)])
            elif leave.customer_selection == 'specific' and leave.category_id:
                domain = [('category_id', 'in', leave.category_id.ids),
                          ('active', '=', True),
                          ('parent_id', '=', False)]
                if company.notification_type == 'email':
                    domain.append(('email', '!=', False))
                else:
                    domain.append('|')
                    domain.extend([('mobile', '!=', False), ('phone', '!=', False)])
                customers_to_notify = self.env['res.partner'].search(domain)
            else:
                customers_to_notify = []

            if not customers_to_notify:
                print(f"  No matching customers for leave {leave.name}")
                continue

            # loop customers
            for customer in customers_to_notify:
                if company.notification_type == 'email':
                    subject_content = template.subject or 'Holiday Notification'
                    body_content = template.body_html or ''
                    if start_date == end_date:
                        start_str = start_date.strftime("%d %b, %Y")
                        end_str = ""
                    else:
                        start_str = start_date.strftime("%d %b, %Y")
                        end_str = end_date.strftime("%d %b, %Y")

                    replacements = {
                        'start_date': start_str,
                        'end_date': end_str,
                        'next_working_date': next_working_date,
                        'holiday_reason': holiday_reason,
                        'holiday_period': holiday_period,
                        'customer.name': customer.name,
                        'user_company_id_name': company.name,
                        'user_email': company.email or '',
                    }
                    for var_name, var_value in replacements.items():
                        subject_content = subject_content.replace(f'{{{{{var_name}}}}}', str(var_value))
                        body_content = body_content.replace(f'{{{{{var_name}}}}}', str(var_value))
                        subject_content = subject_content.replace(f'{{{var_name}}}', str(var_value))
                        body_content = body_content.replace(f'{{{var_name}}}', str(var_value))
                        subject_content = subject_content.replace(f'${{{var_name}}}', str(var_value))
                        body_content = body_content.replace(f'${{{var_name}}}', str(var_value))

                    mail_values = {
                        'subject': subject_content,
                        'body_html': body_content,
                        'email_to': customer.email,
                        'email_from': company.email,
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    print(f"Email sent to {customer.name} ({customer.email})")

                elif company.notification_type == 'whatsapp':
                    mobile = customer.mobile or customer.phone
                    print(f"Sending WhatsApp to {customer.name} ({mobile})")
                    try:
                        if start_date == end_date:
                            start_str = start_date.strftime("%d %b, %Y")
                            end_str = ""
                        else:
                            start_str = start_date.strftime("%d %b, %Y")
                            end_str = end_date.strftime("%d %b, %Y")

                        variables = {
                            'customer': customer,
                            'customer_name': customer.name,
                            'start_date': start_str,
                            'end_date': end_str,
                            'next_working_date': next_working_date,
                            'holiday_reason': holiday_reason,
                            'holiday_period': holiday_period,
                        }

                        whatsapp_template.send_message(
                            to_number=mobile,
                            variables=variables)
                        print(f"WhatsApp sent to {customer.name} ({mobile})")
                    except UserError as e:
                        print(f"Error sending WhatsApp to {customer.name}: {e}")
                    except Exception as e:
                        print(f"Unexpected error sending WhatsApp to {customer.name}: {e}")




    # @api.model
    # def send_holiday_notifications(self):
    #     today = fields.Date.today()
    #     print("Today's date:", today)
    #     company = self.env.company
    #     if not company.notify_customer:
    #         print("Notifications disabled. Exiting.")
    #         return
    #     template = self.env['mail.template'].search(
    #         [('name', '=', 'Holiday Notification')], limit=1)
    #     if not template:
    #         print("No template found. Exiting.")
    #         return
    #     if company.notification_type == 'email':
    #         customers = self.env['res.partner'].search([
    #             ('active', '=', True),
    #             ('email', '!=', False),
    #             ('parent_id', '=', False)])
    #         print("Active customers to notify:", [(c.id, c.name, c.email) for c in customers])
    #     elif company.notification_type == 'whatsapp':
    #         customers = self.env['res.partner'].search([
    #             ('active', '=', True),
    #             ('parent_id', '=', False),
    #             '|', ('mobile', '!=', False), ('phone', '!=', False)])
    #         print("Active customers to notify:", [(c.id, c.name, c.mobile or c.phone) for c in customers])
    #     else:
    #         print("Invalid notification type. Exiting.")
    #         return
    #     model_id = self.env['ir.model'].search([('model', '=', 'hr.leave')], limit=1)
    #     whatsapp_template = self.env['template.whatsapp'].search([('model_id', '=', model_id.id)], limit=1)
    #     if company.notification_type == 'whatsapp' and not whatsapp_template:
    #         print("No WhatsApp template found. Exiting.")
    #         return
    #     leaves = self.search([])
    #     for leave in leaves:
    #         start_date = leave.date_from.date() if leave.date_from else None
    #         end_date = leave.date_to.date() if leave.date_to else start_date
    #         holiday_reason = leave.name or "holidays"
    #         if start_date == end_date:
    #             holiday_period = f"on {start_date.strftime('%d %b, %Y')}"
    #         else:
    #             holiday_period = f"from {start_date.strftime('%d %b, %Y')} to {end_date.strftime('%d %b, %Y')}"
    #         print(f"\nProcessing leave {leave.name or leave.id}, Start Date: {start_date}, End Date: {end_date}")
    #         next_working_date = (end_date + timedelta(days=1)).strftime("%d %b, %Y")
    #         should_send = False
    #         send_reason = ""
    #         if leave.frequency == 'once':
    #             send_date = start_date - timedelta(days=1)
    #             if send_date == today:
    #                 should_send = True
    #                 send_reason = "Once (day before)"
    #         elif leave.frequency == 'daily':
    #             if start_date <= today <= end_date:
    #                 should_send = True
    #                 send_reason = "Daily (during holiday)"
    #         elif leave.frequency == 'both':
    #             send_date = start_date - timedelta(days=1)
    #             if send_date == today:
    #                 should_send = True
    #                 send_reason = "Both (day before)"
    #             elif start_date <= today <= end_date:
    #                 should_send = True
    #                 send_reason = "Both (during holiday)"
    #         if not should_send:
    #             print(f"  Skipping - Today {today} doesn't match frequency {leave.frequency}")
    #             continue
    #         print(f"  Sending notification - Reason: {send_reason}")
    #         for customer in customers:
    #             if company.notification_type == 'email':
    #                 subject_content = template.subject or 'Holiday Notification'
    #                 body_content = template.body_html or ''
    #                 if start_date == end_date:
    #                     start_str = start_date.strftime("%d %b, %Y")
    #                     end_str = ""
    #                 else:
    #                     start_str = start_date.strftime("%d %b, %Y")
    #                     end_str = end_date.strftime("%d %b, %Y")
    #                 replacements = {
    #                     'start_date': start_str,
    #                     'end_date': end_str,
    #                     'next_working_date': next_working_date,
    #                     'holiday_reason': holiday_reason,
    #                     'holiday_period': holiday_period,
    #                     'customer.name': customer.name,
    #                     'user_company_id_name': company.name,
    #                     'user_email': company.email or '',
    #                 }
    #                 for var_name, var_value in replacements.items():
    #                     subject_content = subject_content.replace(f'{{{{{var_name}}}}}', str(var_value))
    #                     body_content = body_content.replace(f'{{{{{var_name}}}}}', str(var_value))
    #                     subject_content = subject_content.replace(f'{{{var_name}}}', str(var_value))
    #                     body_content = body_content.replace(f'{{{var_name}}}', str(var_value))
    #                     subject_content = subject_content.replace(f'${{{var_name}}}', str(var_value))
    #                     body_content = body_content.replace(f'${{{var_name}}}', str(var_value))
    #                 mail_values = {
    #                     'subject': subject_content,
    #                     'body_html': body_content,
    #                     'email_to': customer.email,
    #                     'email_from': company.email,
    #                 }
    #                 self.env['mail.mail'].create(mail_values).send()
    #                 print(f"Email sent to {customer.name} ({customer.email})")
    #             elif company.notification_type == 'whatsapp':
    #                 mobile = customer.mobile or customer.phone
    #                 print(f"Sending WhatsApp to {customer.name} ({mobile})")
    #                 try:
    #                     if start_date == end_date:
    #                         start_str = start_date.strftime("%d %b, %Y")
    #                         end_str = ""
    #                     else:
    #                         start_str = start_date.strftime("%d %b, %Y")
    #                         end_str = end_date.strftime("%d %b, %Y")
    #                     variables = {
    #                         'customer': customer,
    #                         'customer_name': customer.name,
    #                         'start_date': start_str,
    #                         'end_date': end_str,
    #                         'next_working_date': next_working_date,
    #                         'holiday_reason': holiday_reason,
    #                         'holiday_period': holiday_period }
    #
    #                     whatsapp_template.send_message(
    #                         to_number=mobile,
    #                         variables=variables)
    #                     print(f"WhatsApp sent to {customer.name} ({mobile})")
    #                 except UserError as e:
    #                     print(f"Error sending WhatsApp to {customer.name}: {e}")
    #                 except Exception as e:
    #                     print(f"Unexpected error sending WhatsApp to {customer.name}: {e}")


 #    @api.model
 #    def send_holiday_notifications(self):
 #        today = fields.Date.today()
 #        print("Today's date:", today)
 #
 #        company = self.env.company
 #        if not company.notify_customer:
 #            print("Notifications disabled. Exiting.")
 #            return
 #
 #        # Fetch template dynamically by name (instead of XML-ID)
 #        template = self.env['mail.template'].search(
 #            [('name', '=', 'Holiday Notification')], limit=1)
 #        if not template:
 #            print("No template found. Exiting.")
 #            return
 #
 #        if company.notification_type == 'email':
 #            customers = self.env['res.partner'].search([
 #                ('active', '=', True),
 #                ('email', '!=', False),
 #                ('parent_id', '=', False),
 #            ])
 #            print("Active customers to notify:", [(c.id, c.name, c.email) for c in customers])
 #        elif company.notification_type == 'whatsapp':
 #            customers = self.env['res.partner'].search([
 #                ('active', '=', True),
 #                ('parent_id', '=', False),
 #                '|', ('mobile', '!=', False), ('phone', '!=', False)
 #            ])
 #            print("Active customers to notify:", [(c.id, c.name, c.mobile or c.phone) for c in customers])
 #        else:
 #            print("Invalid notification type. Exiting.")
 #            return
 #
 #        model_id = self.env['ir.model'].search([('model', '=', 'hr.leave')], limit=1)
 #        whatsapp_template = self.env['template.whatsapp'].search([('model_id', '=', model_id.id)], limit=1)
 #
 #        if company.notification_type == 'whatsapp' and not whatsapp_template:
 #            print("No WhatsApp template found. Exiting.")
 #            return
 #
 #        # Get the current user for template variables
 #        company_name = company.name
 #        user_email = company.email
 #
 #        leaves = self.search([])
 #        for leave in leaves:
 #            start_date = leave.date_from.date() if leave.date_from else None
 #            end_date = leave.date_to.date() if leave.date_to else start_date
 #            holiday_reason = leave.name or "holidays"
 #            if not start_date:
 #                continue
 #
 #            print(f"\nProcessing leave {leave.name or leave.id}, Start Date: {start_date}, End Date: {end_date}")
 #            next_working_date = (end_date + timedelta(days=1)).strftime("%d %b, %Y")
 #
 #            should_send = False
 #            send_reason = ""
 #
 #            if leave.frequency == 'once':
 #                # Send one day before the holiday starts
 #                send_date = start_date - timedelta(days=1)
 #                if send_date == today:
 #                    should_send = True
 #                    send_reason = "Once (day before)"
 #
 #            elif leave.frequency == 'daily':
 #                # Send every day during the holiday period
 #                if start_date <= today <= end_date:
 #                    should_send = True
 #                    send_reason = "Daily (during holiday)"
 #
 #            elif leave.frequency == 'both':
 #                # Send day before AND every day during holiday
 #                send_date = start_date - timedelta(days=1)
 #                if send_date == today:
 #                    should_send = True
 #                    send_reason = "Both (day before)"
 #                elif start_date <= today <= end_date:
 #                    should_send = True
 #                    send_reason = "Both (during holiday)"
 #
 #            if not should_send:
 #                print(f"  Skipping - Today {today} doesn't match frequency {leave.frequency}")
 #                continue
 #
 #            print(f"  Sending notification - Reason: {send_reason}")
 #
 #            for customer in customers:
 #                if company.notification_type == 'email':
 #                    # Get template content
 #                    subject_content = template.subject or 'Holiday Notification'
 #                    body_content = template.body_html or ''
 #
 #                    # Replace variables manually - handle both {{variable}} and {variable} syntax
 #                    replacements = {
 #                        # 'customer_name': customer.name,
 #                        'start_date': start_date.strftime("%d %b, %Y") if start_date else '',
 #                        'end_date': end_date.strftime("%d %b, %Y") if end_date else '',
 #                        'next_working_date': next_working_date,
 #                        'holiday_reason': holiday_reason,
 #                        'customer.name': customer.name,
 #                        'user_company_id_name': company.name,
 #                        'user_email': company.email or '',
 #                    }
 #
 #                    # Replace all variable patterns
 #                    for var_name, var_value in replacements.items():
 #                        subject_content = subject_content.replace(f'{{{{{var_name}}}}}', str(var_value))
 #                        body_content = body_content.replace(f'{{{{{var_name}}}}}', str(var_value))
 #
 #                        # Handle single curly braces {variable}
 #                        subject_content = subject_content.replace(f'{{{var_name}}}', str(var_value))
 #                        body_content = body_content.replace(f'{{{var_name}}}', str(var_value))
 #
 #                        # Handle dollar sign variables ${variable}
 #                        subject_content = subject_content.replace(f'${{{var_name}}}', str(var_value))
 #                        body_content = body_content.replace(f'${{{var_name}}}', str(var_value))
 #
 #                        # Create and send email
 #                    mail_values = {
 #                        'subject': subject_content,
 #                        'body_html': body_content,
 #                        'email_to': customer.email,
 #                        'email_from': company.email,
 #                    }
 #
 #                    self.env['mail.mail'].create(mail_values).send()
 #
 #                    print(f"Email sent to {customer.name} ({customer.email})")
 #
 #                elif company.notification_type == 'whatsapp':
 #                    mobile = customer.mobile or customer.phone
 #                    print(f"Sending WhatsApp to {customer.name} ({mobile})")
 #                    try:
 #                        variables = {
 #                            'customer': customer,
 #                            'customer_name': customer.name,
 #                            'start_date': start_date.strftime("%d %b, %Y") if start_date else '',
 #                            'end_date': end_date.strftime("%d %b, %Y") if end_date else '',
 #                            'next_working_date': next_working_date,
 #                            'holiday_reason': holiday_reason
 #                        }
 #
 #                        whatsapp_template.send_message(
 #                            to_number=mobile,
 #                            variables=variables)
 #                        print(f"WhatsApp sent to {customer.name} ({mobile})")
 #                    except UserError as e:
 #                        print(f"Error sending WhatsApp to {customer.name}: {e}")
 #                    except Exception as e:
 #                        print(f"Unexpected error sending WhatsApp to {customer.name}: {e}")
 #
 #