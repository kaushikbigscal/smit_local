from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class MatrixWebhookController(http.Controller):

    @http.route('/api/matrix/attendance_webhook',
                type='http', auth='none', methods=['POST'], csrf=False)
    def attendance_webhook(self, **kw):
        try:
            raw = request.httprequest.data.decode('utf-8')
            data = json.loads(raw)
        except Exception as e:
            _logger.error(f"[MATRIX] Invalid JSON: {e}")
            return Response(
                json.dumps({"status": "error", "message": "Invalid JSON"}),
                content_type='application/json',
                status=400
            )

        _logger.info(f"[MATRIX] Received: {data}")

        # Normalize to list
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict) and isinstance(data.get("events"), list):
            events = data["events"]
        else:
            events = [data]

        Attendance = request.env['hr.attendance'].sudo()
        results = []

        for event in events:
            try:
                result = Attendance.process_matrix_event(event)
                results.append(result)
            except Exception as ex:
                results.append({
                    "userid": event.get("userid"),
                    "status": "error",
                    "message": str(ex)
                })

        return Response(
            json.dumps({"status": "ok", "count": len(results), "results": results}),
            content_type='application/json',
            status=200
        )
