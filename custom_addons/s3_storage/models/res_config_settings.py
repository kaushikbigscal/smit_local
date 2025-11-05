'''
Created on Nov 10, 2020

@author: Zuhair Hammadi
'''
from odoo import models, fields, api, _
from odoo.tools import config
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    attachment_location = fields.Selection([('s3', 'S3 Storage'), ('file', 'File System'), ('db', 'Database')], required = True, default = 'file', config_parameter='ir_attachment.location')
    aws_access_key_id = fields.Char(string="Access Key ID")
    aws_secret_access_key = fields.Char(string="Secret Access Key")
    aws_region_name = fields.Char(string="Region Name")
    aws_endpoint_url = fields.Char(string="AWS Endpoint URL")
    
    aws_api_version = fields.Char(string="AWS API Version")
    aws_use_ssl = fields.Boolean(string="AWS Use SSL")
    aws_verify = fields.Char(string="AWS Verify")
    
    s3_bucket = fields.Char(string="AWS S3 Bucket")
    s3_delete = fields.Boolean(string="S3 Delete", config_parameter='ir_attachment.s3_delete', help='Delete s3 file when attachment deleted')
    s3_cache = fields.Boolean(string="Use S3 Cache", config_parameter='ir_attachment.s3_cache', help='Cache in file system')
        
    def get_values(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        
        res = super(ResConfigSettings, self).get_values()
        
        for fname in ['s3_bucket', 'aws_access_key_id', 'aws_secret_access_key', 'aws_region_name','aws_endpoint_url','aws_api_version','aws_use_ssl','aws_verify']:
            value = get_param('ir_attachment.%s' % fname) or config.get(fname)
            if self._fields[fname].type == 'boolean':
                value = bool(value)
            res[fname] = value
        
        return res
    
    
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        
        set_param = self.env['ir.config_parameter'].sudo().set_param
        
        for fname in ['s3_bucket', 'aws_access_key_id', 'aws_secret_access_key', 'aws_region_name','aws_endpoint_url','aws_api_version','aws_use_ssl','aws_verify']:
            value = self[fname]
            config_parameter = 'ir_attachment.%s' % fname
            if value == config.get(fname):
                set_param(config_parameter, False)
            else:
                set_param(config_parameter, value)

    @api.model
    def action_migrate_attachments_to_filestore(self, *args, **kwargs):
        """Migrate all S3-backed attachments back into the file store."""
        Attachment = self.env['ir.attachment'].sudo()
        s3_attachments = Attachment.search([('s3_key', '!=', False)])
        if not s3_attachments:
            raise UserError(_("No attachments are currently stored in S3."))

        migrated = 0
        # wrap in a SAVEPOINT so we can rollback on error
        self.env.cr.execute('SAVEPOINT migrate_attach')
        for attach in s3_attachments:
            data = attach._s3_read_binary(attach.s3_key)
            if not data:
                _logger.warning("Skipping attachment %s: failed to read from S3", attach.id)
                continue
            fname = attach._file_write(data, attach.checksum)
            attach.write({
                'store_fname': fname,
                'db_datas': data,
                's3_key': False,
            })
            migrated += 1

        try:
            self.env.cr.execute('RELEASE SAVEPOINT migrate_attach')
        except Exception:
            self.env.cr.execute('ROLLBACK TO SAVEPOINT migrate_attach')
            raise

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Migration Complete'),
                'message': _("%d attachments migrated to filestore.") % migrated,
                'type': 'success',
                'sticky': False,
            }
        }