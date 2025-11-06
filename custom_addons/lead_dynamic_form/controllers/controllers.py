from odoo import http
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)


class JobApplicationController(http.Controller):

    @http.route('/job/application/form', type='http', auth='public', website=True)
    def job_application_form(self, lead_id=None):
        lead = None
        if lead_id:
            lead = request.env['crm.lead'].sudo().browse(int(lead_id))
        return request.render('lead_dynamic_form.job_application_form_template', {
            'lead': lead
        })

    @http.route(['/job/application/submit'], type='http', auth='public', website=True, csrf=True)
    def job_application_submit(self, **post):
        """Handle form submission and save resume attachment."""
        _logger.info("Job application form submitted with data: %s", post)

        try:
            lead_id = post.get('lead_id')
            lead = None

            if lead_id:
                try:
                    lead = request.env['crm.lead'].sudo().browse(int(lead_id))
                    if lead.exists():
                        _logger.info("Lead found: %s", lead.name)
                    else:
                        _logger.warning("Lead ID %s does not exist.", lead_id)
                        lead = None
                except ValueError:
                    _logger.error("Invalid Lead ID provided: %s", lead_id)

                # Handle resume upload
                if 'resume' in request.httprequest.files:
                    resume_file = request.httprequest.files['resume']
                    if resume_file and resume_file.filename:
                        try:
                            file_content = resume_file.read()
                            filename = resume_file.filename

                            # Post that file was uploaded
                            lead.message_post(
                                body=f"Resume uploaded: {filename}",
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                                attachments=[(filename, file_content)]
                            )
                            _logger.info("Resume posted to chatter for lead %s", lead.id)

                        except Exception as e:
                            _logger.error("Error uploading resume for lead %s: %s", lead.id, str(e))
                            return request.render('lead_dynamic_form.thank_you_template', {
                                'success': False,
                                'error': f"Error uploading resume: {str(e)}",
                                'lead_id': lead_id
                            })
                    else:
                        _logger.warning("Resume file is missing or empty for lead %s", lead.id)
                else:
                    _logger.info("No resume file was uploaded in this request.")

            else:
                _logger.warning("No valid lead found. Chatter update skipped.")

            return request.render('lead_dynamic_form.thank_you_template', {
                'success': True,
                'lead_id': lead_id
            })

        except Exception as e:
            _logger.error("Unexpected error during job application processing: %s", str(e))
            return request.render('lead_dynamic_form.thank_you_template', {
                'success': False,
                'error': str(e)
            })
