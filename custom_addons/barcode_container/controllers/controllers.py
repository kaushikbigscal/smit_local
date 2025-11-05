from odoo import http
from odoo.http import request
import json


class ContainerController(http.Controller):

    @http.route("/barcode/container/scan", type="http", auth="user", methods=["GET", "POST"], website=True, csrf=False)
    def scan_container(self, container_id=None, label=None, **kw):
        """
        Handles QR code scanning for container lines.
        Supports both GET (direct URL access) and POST (AJAX from portal scanner).
        If one line with a label is scanned, all lines with the same label in that container will be marked as scanned.
        """
        is_ajax = False

        # 🔹 Parse JSON body for AJAX request
        if request.httprequest.method == "POST":
            content_type = request.httprequest.content_type or ""
            if "application/json" in content_type:
                is_ajax = True
                try:
                    json_data = json.loads(request.httprequest.data.decode('utf-8'))
                    params = json_data.get("params", {})
                    container_id = params.get("container_id") or container_id
                    label = params.get("label") or label
                except Exception as e:
                    return request.make_json_response({
                        "success": False,
                        "matched": False,
                        "error": "Invalid JSON",
                        "message": str(e)
                    })

        # 🔹 Validate required params
        if not container_id or not label:
            if is_ajax:
                return request.make_json_response({
                    "success": False,
                    "matched": False,
                    "error": "missing_params",
                    "message": "Container ID and Label are required"
                })
            else:
                request.session['container_scan_message'] = {
                    'type': 'warning',
                    'message': 'Missing container ID or label in QR code.'
                }
                return request.redirect("/my/containers")

        # 🔹 Find all matching lines (same container + same label)
        ContainerLine = request.env["barcode.container.line"].sudo()
        lines = ContainerLine.search([
            ("container_id", "=", int(container_id)),
            ("label", "=", label)
        ])

        if not lines:
            # No match
            if is_ajax:
                return request.make_json_response({
                    "success": False,
                    "matched": False,
                    "error": "no_match",
                    "message": f"No matching line found for label: {label}"
                })
            else:
                request.session['container_scan_message'] = {
                    'type': 'danger',
                    'message': f'No matching line found for label: {label}'
                }
                return request.redirect("/my/containers")

        # 🔹 Check if already scanned
        already_scanned_count = lines.filtered(lambda l: l.scanned).__len__()

        # 🔹 Mark all lines as scanned
        lines.write({"scanned": True})

        # Prepare response data
        container = lines[0].container_id
        container_name = container.name or ""
        container_id_val = container.id

        if already_scanned_count == len(lines):
            message = f"All lines with label '{label}' were already scanned previously."
            msg_type = "info"
        elif already_scanned_count > 0:
            message = f"Some lines with label '{label}' were already scanned; remaining have now been marked as scanned."
            msg_type = "info"
        else:
            message = f"✅ All lines with label '{label}' marked as scanned successfully!"
            msg_type = "success"

        # 🔹 Return responses
        if is_ajax:
            return request.make_json_response({
                "success": True,
                "matched": True,
                "label": label,
                "container_name": container_name,
                "container_id": container_id_val,
                "already_scanned": already_scanned_count > 0,
                "message": message,
                "redirect_url": f"/my/container/{container_id_val}"
            })
        else:
            request.session['container_scan_message'] = {
                'type': msg_type,
                'message': message
            }
            return request.redirect(f"/my/container/{container_id_val}")


# from odoo import http
# from odoo.http import request
# import json
#
#
# class ContainerController(http.Controller):
#
#     @http.route("/barcode/container/scan", type="http", auth="user", methods=["GET", "POST"], website=True, csrf=False)
#     def scan_container(self, container_id=None, label=None, **kw):
#         """
#         Handles QR code scanning for container lines.
#         Supports both GET (direct URL access) and POST (AJAX from portal scanner).
#         """
#         is_ajax = False
#
#         # Check if this is an AJAX/JSON request
#         if request.httprequest.method == "POST":
#             content_type = request.httprequest.content_type or ""
#             if "application/json" in content_type:
#                 is_ajax = True
#                 try:
#                     # Parse JSON body manually
#                     json_data = json.loads(request.httprequest.data.decode('utf-8'))
#                     params = json_data.get("params", {})
#                     container_id = params.get("container_id") or container_id
#                     label = params.get("label") or label
#                 except Exception as e:
#                     return request.make_json_response({
#                         "success": False,
#                         "matched": False,
#                         "error": "Invalid JSON",
#                         "message": str(e)
#                     })
#
#         # Validate inputs
#         if not container_id or not label:
#             if is_ajax:
#                 return request.make_json_response({
#                     "success": False,
#                     "matched": False,
#                     "error": "missing_params",
#                     "message": "Container ID and Label are required"
#                 })
#             else:
#                 # For direct URL access, show notification via session
#                 request.session['container_scan_message'] = {
#                     'type': 'warning',
#                     'message': 'Missing container ID or label in QR code.'
#                 }
#                 return request.redirect("/my/containers")
#
#         # Search for the container line
#         ContainerLine = request.env["barcode.container.line"].sudo()
#         line = ContainerLine.search([
#             ("container_id", "=", int(container_id)),
#             ("label", "=", label)
#         ], limit=1)
#
#         if not line:
#             # Line not found
#             if is_ajax:
#                 return request.make_json_response({
#                     "success": False,
#                     "matched": False,
#                     "error": "no_match",
#                     "message": f"No matching line found for label: {label}"
#                 })
#             else:
#                 request.session['container_scan_message'] = {
#                     'type': 'danger',
#                     'message': f'No matching line found for label: {label}'
#                 }
#                 return request.redirect("/my/containers")
#
#         # Check if already scanned
#         was_already_scanned = line.scanned
#
#         # Mark as scanned
#         line.sudo().write({"scanned": True})
#
#         container_name = line.container_id.name or ""
#         container_id_val = line.container_id.id
#
#         # Prepare success message
#         if was_already_scanned:
#             message = f"Line '{label}' was already scanned previously."
#             msg_type = "info"
#         else:
#             message = f"✅ Line '{label}' marked as scanned successfully!"
#             msg_type = "success"
#
#         if is_ajax:
#             # Return JSON for AJAX requests
#             return request.make_json_response({
#                 "success": True,
#                 "matched": True,
#                 "label": label,
#                 "container_name": container_name,
#                 "container_id": container_id_val,
#                 "already_scanned": was_already_scanned,
#                 "message": message,
#                 "redirect_url": f"/my/container/{container_id_val}"
#             })
#         else:
#             # For direct URL access, set session message and redirect
#             request.session['container_scan_message'] = {
#                 'type': msg_type,
#                 'message': message
#             }
#             return request.redirect(f"/my/container/{container_id_val}")
