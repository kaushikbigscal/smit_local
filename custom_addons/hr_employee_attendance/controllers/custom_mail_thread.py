from odoo import http
from odoo.http import request


class MailThreadController(http.Controller):

    @http.route("/web/custom_thread_data_messages", type="json", auth="user")
    def mail_thread_data_messages(self, thread_model, thread_id):
        """
        Unified Controller: Fetches both thread data and messages.
        - Retrieves thread information (activities, attachments, followers, recipients, suggested recipients).
        - Fetches messages related to the thread.
        """

        # Ensure request_list is not None
        request_list = ["activities", "attachments", "followers"]

        # Fetch the thread safely
        thread = request.env[thread_model].sudo().browse(thread_id)
        if not thread.exists():
            return {"error": "Thread not found"}

        # Prepare response data
        response_data = thread._get_mail_thread_data(request_list)

        # Fetch messages
        domain = [
            ("res_id", "=", int(thread_id)),
            ("model", "=", thread_model),
            ("message_type", "!=", "user_notification"),
        ]
        res = request.env["mail.message"]._message_fetch(domain)

        # Ensure message processing only for non-public users
        if not request.env.user._is_public() and res.get("messages"):
            res["messages"].set_message_done()

        # Add messages to the response
        response_data["messages"] = res["messages"].message_format()

        return response_data
