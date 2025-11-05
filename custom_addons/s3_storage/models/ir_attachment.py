# TODO:: FIXED PRE-SIGNED URLs Implementation

from odoo import models, fields, api, _
from odoo.tools import config
from odoo.exceptions import UserError
import boto3
import logging
import os
import time
import datetime
from collections import defaultdict
import shutil
from odoo.osv import expression
from odoo.http import Stream, Response
import base64
from odoo.addons.base.models.ir_http import IrHttp

_logger = logging.getLogger(__name__)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def patch_http_stream():
    """
    FIXED: Patch HTTP stream to properly handle S3 presigned URLs
    """
    if 'patch_http_stream_presigned_fixed' in repr(Stream.from_attachment):
        return

    @classmethod
    def from_attachment(cls, attachment):
        """Modified to handle S3 presigned URLs properly"""

        if hasattr(attachment, 's3_key') and attachment.s3_key:
            # Generate presigned URL for S3 attachments
            presigned_url = attachment._get_presigned_url()
            print("Form Attachmenrt", presigned_url)
            if presigned_url:
                # Create a custom stream that returns the presigned URL
                class S3PresignedStream:
                    def __init__(self, url, attachment):
                        self.url = url
                        self.attachment = attachment
                        self.type = 'url'
                        self.mimetype = attachment.mimetype or 'application/octet-stream'
                        self.size = attachment.file_size or 0
                        self.last_modified = attachment.write_date or fields.Datetime.now()
                        self.etag = attachment.checksum

                    def get_response(self, **kwargs):
                        """Return redirect response to presigned URL"""
                        response = Response()
                        response.status_code = 302  # Temporary redirect
                        response.headers['Location'] = self.url
                        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                        response.headers['Pragma'] = 'no-cache'
                        response.headers['Expires'] = '0'

                        # Security headers
                        response.headers['X-Content-Type-Options'] = 'nosniff'
                        response.headers['X-Frame-Options'] = 'SAMEORIGIN'

                        # Add CORS headers for cross-origin requests
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Access-Control-Allow-Methods'] = 'GET'
                        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

                        _logger.info(f"Redirecting to S3 presigned URL: {self.url}")
                        return response

                return S3PresignedStream(presigned_url, attachment)
            else:
                _logger.warning(f"Failed to generate presigned URL for attachment {attachment.id}, falling back")

        # Use original method for non-S3 attachments or fallback
        return from_attachment.origin(attachment)

    from_attachment.origin = Stream.from_attachment
    Stream.from_attachment = from_attachment


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    s3_key = fields.Char(index=True, readonly=True)
    content_location = fields.Selection([
        ('db', 'Database'),
        ('file', 'File System'),
        ('s3', 'S3 Object Storage')
    ], compute='_calc_content_location')

    # New fields for presigned URL functionality
    presigned_url_cache = fields.Char(help="Cached presigned URL")
    presigned_url_expires = fields.Datetime(help="When the cached presigned URL expires")
    access_token = fields.Char(help="Security token for URL validation")

    @api.depends('s3_key', 'store_fname')
    def _calc_content_location(self):
        for record in self:
            if record.s3_key:
                record.content_location = 's3'
            elif record.store_fname:
                record.content_location = 'file'
            else:
                record.content_location = 'db'

    @api.model
    def get_s3_client(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param

        region_name = get_param('ir_attachment.aws_region_name') or config.get('aws_region_name')
        api_version = get_param('ir_attachment.aws_api_version') or config.get('aws_api_version')
        use_ssl = bool(get_param('ir_attachment.aws_use_ssl') or config.get('aws_use_ssl'))
        verify = get_param('ir_attachment.aws_verify') or config.get('aws_verify')
        endpoint_url = get_param('ir_attachment.aws_endpoint_url') or config.get('aws_endpoint_url')
        aws_access_key_id = get_param('ir_attachment.aws_access_key_id') or config.get('aws_access_key_id')
        aws_secret_access_key = get_param('ir_attachment.aws_secret_access_key') or config.get('aws_secret_access_key')

        if verify == 'False':
            verify = False

        return boto3.client('s3', region_name=region_name, api_version=api_version, use_ssl=use_ssl, verify=verify,
                            endpoint_url=endpoint_url, aws_access_key_id=aws_access_key_id,
                            aws_secret_access_key=aws_secret_access_key)

    @api.model
    def recover_s3_attachments(self):
        """
        Attempt to recover S3 attachments that lost their s3_key during uninstall
        This method tries to match orphaned attachments with S3 files
        """
        import boto3
        from botocore.exceptions import ClientError

        _logger.info("Starting S3 attachment recovery process...")

        try:
            # Find attachments with no data and no s3_key (potential orphans)
            orphaned_attachments = self.search([
                ('raw', '=', b''),
                ('db_datas', '=', False),
                ('store_fname', '=', False),
                ('s3_key', '=', False),
                ('checksum', '!=', False),  # Must have checksum to find S3 file
            ])

            _logger.info(f"Found {len(orphaned_attachments)} potentially orphaned attachments")

            if not orphaned_attachments:
                _logger.info("No orphaned attachments found")
                return

            s3_client = self.get_s3_client()
            s3_bucket = self._s3_bucket()

            recovered_count = 0

            for attachment in orphaned_attachments:
                try:
                    # Try to reconstruct the S3 key from checksum
                    checksum = attachment.checksum
                    if not checksum:
                        continue

                    # Your S3 key format: checksum[:2]/checksum[2:4]/checksum
                    potential_key = f"{checksum[:2]}/{checksum[2:4]}/{checksum}"
                    s3_key = f"{self._cr.dbname}/{potential_key}"

                    # Check if file exists in S3
                    try:
                        s3_client.head_object(Bucket=s3_bucket, Key=s3_key)

                        # File exists! Restore the s3_key
                        attachment.write({
                            's3_key': potential_key
                        })

                        _logger.info(f"Recovered attachment {attachment.id} -> {potential_key}")
                        recovered_count += 1

                    except ClientError as e:
                        if e.response['Error']['Code'] == '404':
                            # File doesn't exist in S3, skip
                            continue
                        else:
                            raise

                except Exception as e:
                    _logger.error(f"Error recovering attachment {attachment.id}: {e}")
                    continue

            _logger.info(f"Recovery completed: {recovered_count} attachments recovered")
            return recovered_count

        except Exception as e:
            _logger.error(f"S3 recovery process failed: {e}")
            raise

    @api.model
    def _s3_bucket(self):
        res = self.env['ir.config_parameter'].sudo().get_param("ir_attachment.s3_bucket") or config.get('s3_bucket')
        if not res:
            raise UserError(_('Please set config s3_bucket'))
        return res

    @api.model
    def _get_presigned_url_config(self):
        """Get presigned URL configuration parameters"""
        get_param = self.env['ir.config_parameter'].sudo().get_param
        return {
            'expiration': int(get_param('ir_attachment.presigned_url_expiration', 3600)),  # 1 hour default
            'use_security_token': bool(get_param('ir_attachment.presigned_url_security_token', True)),
            'content_disposition': get_param('ir_attachment.presigned_url_content_disposition', 'inline'),
            # Changed to inline for PDF viewing
            'cache_urls': bool(get_param('ir_attachment.presigned_url_cache', True)),
        }

    def _get_presigned_url(self, expiration=None):
        """Generate presigned URL for S3 object - FIXED VERSION"""

        if self._is_static_asset():
            _logger.debug(f"Skipping S3 presigned URL for static asset: {self.name}")
            return False

        if not self.s3_key:
            _logger.warning(f"Attempting to generate presigned URL for attachment {self.id} without s3_key")
            return False
        print("started")
        config = self._get_presigned_url_config()
        expiration = expiration or config['expiration']

        # Check if we have a valid cached URL
        if (config['cache_urls'] and
                self.presigned_url_cache and
                self.presigned_url_expires and
                self.presigned_url_expires > fields.Datetime.now()):
            _logger.debug(f"Using cached presigned URL for attachment {self.id}")
            return self.presigned_url_cache

        try:
            s3_client = self.get_s3_client()
            s3_bucket = self._s3_bucket()
            s3_key = f"{self._cr.dbname}/{self.s3_key}"

            # Prepare parameters for presigned URL
            params = {
                'Bucket': s3_bucket,
                'Key': s3_key,
            }

            # FIXED: Set content disposition based on file type
            if self.name:
                if self.mimetype and 'pdf' in self.mimetype.lower():
                    # For PDFs, use inline disposition to allow viewing
                    params['ResponseContentDisposition'] = f'inline; filename="{self.name}"'
                else:
                    # For other files, use the configured disposition
                    print("Hello COnfig")
                    params['ResponseContentDisposition'] = f'{config["content_disposition"]}; filename="{self.name}"'

            # Set content type to ensure proper handling
            if self.mimetype:
                params['ResponseContentType'] = self.mimetype
            print("I am here trying")
            # Generate the presigned URL
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiration
            )
            print("URL", presigned_url)
            # Cache the URL if caching is enabled
            if config['cache_urls']:
                expires_at = fields.Datetime.now() + datetime.timedelta(seconds=expiration - 60)  # 1 minute buffer
                self.sudo().write({
                    'presigned_url_cache': presigned_url,
                    'presigned_url_expires': expires_at
                })

            _logger.info(f"Generated presigned URL for attachment {self.id}: {presigned_url}")
            return presigned_url

        except Exception as e:
            _logger.error(f"Failed to generate presigned URL for attachment {self.id}: {e}")
            _logger.exception(e)
            return False

    def get_download_url(self):
        """Public method to get download URL - Returns presigned URL for S3 files"""
        self.ensure_one()
        if self.s3_key:
            presigned_url = self._get_presigned_url()
            if presigned_url:
                return presigned_url
            else:
                # Fallback to traditional URL if presigned URL fails
                return f'/web/content/{self.id}?download=true'
        else:
            # For non-S3 attachments, return traditional Odoo download URL
            return f'/web/content/{self.id}?download=true'

    @api.depends('store_fname', 'db_datas', 's3_key')
    def _compute_raw(self):
        """Modified to handle S3 attachments properly"""
        for attach in self:
            if attach.s3_key:
                # For S3 attachments, always provide the raw data for form display
                # The presigned URL logic is handled separately in the HTTP controller
                try:
                    raw_data = attach._s3_read_binary(attach.s3_key)
                    attach.raw = raw_data
                except Exception as e:
                    _logger.error(f"Failed to read S3 binary data for attachment {attach.id}: {e}")
                    attach.raw = b''
            else:
                # Handle non-S3 attachments with original logic
                if attach.store_fname:
                    attach.raw = attach._file_read(attach.store_fname)
                else:
                    attach.raw = attach.db_datas or b''

    # FIXED: Override datas property to handle S3 attachments
    @api.depends('raw', 'datas')
    def _compute_datas(self):
        """Override to handle S3 attachments properly"""
        for attach in self:
            if attach.s3_key:
                # For S3 attachments, compute datas from raw data
                attach.datas = base64.b64encode(attach.raw or b'').decode('ascii')
            else:
                # Use standard computation for non-S3 attachments
                super(IrAttachment, attach)._compute_datas()

    # The Rest of your existing methods remain the same...
    def _move_content(self, attachment_storage):
        self = self.with_context(attachment_storage=self._storage())
        for attach in self:
            if attach.content_location == attachment_storage:
                continue
            # For S3 migration, we still need binary data temporarily
            if attachment_storage == 's3':
                raw_data = attach._get_binary_data()  # Get binary from current storage
                attach.write({'raw': raw_data, 'mimetype': attach.mimetype})
            else:
                attach.write({'raw': attach.raw, 'mimetype': attach.mimetype})

    def _get_binary_data(self):
        """Helper method to get binary data from current storage location"""
        if self.s3_key:
            return self._s3_read_binary(self.s3_key)
        elif self.store_fname:
            return self._file_read(self.store_fname)
        else:
            return self.db_datas or b''

    @api.model
    def _s3_read_binary(self, key):
        """Keep binary read method for internal operations (migration, etc.)"""
        s3_bucket = self._s3_bucket()
        s3_key = '%s/%s' % (self._cr.dbname, key)
        try:
            value = self.get_s3_client().get_object(Bucket=s3_bucket, Key=s3_key)['Body'].read()
            return value
        except Exception as e:
            _logger.error('_s3_read_binary error %s %s' % (s3_key, type(e)))
            _logger.exception(e)
            return b''

    @api.model
    def _s3_write(self, value, checksum):
        s3_bucket = self._s3_bucket()
        key = '%s/%s/%s' % (checksum[:2], checksum[2:4], checksum)
        s3_key = '%s/%s' % (self._cr.dbname, key)
        self.get_s3_client().put_object(Bucket=s3_bucket, Key=s3_key, Body=value)
        return key

    def _get_datas_related_values(self, data, mimetype):
        checksum = self._compute_checksum(data)
        try:
            index_content = self._index(data, mimetype, checksum=checksum)
        except TypeError:
            index_content = self._index(data, mimetype)
        values = {
            'file_size': len(data),
            'checksum': checksum,
            'index_content': index_content,
            'store_fname': False,
            'db_datas': False,
            's3_key': False
        }

        if data:
            # Check if this is a static asset that should NOT go to S3
            if self._is_static_asset():
                # Force static assets to use database storage
                values['db_datas'] = data
                _logger.debug(f"Static asset {self.name} stored in database, not S3")
            else:
                # Use configured storage for non-static assets
                location = self._context.get('attachment_storage') or self._storage()
                if location == 'file':
                    values['store_fname'] = self._file_write(data, values['checksum'])
                elif location == 's3':
                    values['s3_key'] = self._s3_write(data, values['checksum'])
                else:
                    values['db_datas'] = data
        return values

    def _is_static_asset(self):
        """Check if this attachment is a static web asset that should not be stored in S3"""
        # Check by mimetype
        static_mimetypes = [
            'text/css',
            'application/javascript',
            'application/x-javascript',
            'application/font-woff',
            'application/font-woff2',
            'font/woff',
            'font/woff2',
            'text/html',
            'application/json',
            'text/xml',
            'application/xml',
        ]

        if self.mimetype in static_mimetypes:
            return True

        # Check by name patterns
        if self.name:
            static_extensions = ['.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.svg', '.html', '.json', '.xml']
            if any(self.name.lower().endswith(ext) for ext in static_extensions):
                return True

        # Check by res_model (web assets are usually linked to ir.ui.view or ir.asset)
        if self.res_model in ['ir.ui.view', 'ir.asset', 'ir.qweb']:
            return True

        # Check by res_field (web assets often have specific field names)
        if self.res_field and any(field in self.res_field.lower() for field in ['css', 'js', 'asset', 'bundle']):
            return True

        # IMPORTANT: Don't treat binary fields as static assets
        # Binary fields (like file uploads) should go to S3 if configured
        if self.res_field and 'binary' in self.res_field.lower():
            return False

        return False

    @api.model
    def _get_storage_domain(self):
        """Return a domain to find attachments not yet in the current storage."""
        storage = self._storage()  # 'db', 'file' or 's3'
        return {
            'db': ['|', ('store_fname', '!=', False), ('s3_key', '!=', False)],
            'file': ['|', ('db_datas', '!=', False), ('s3_key', '!=', False)],
            's3': ['|', ('db_datas', '!=', False), ('store_fname', '!=', False)],
        }[storage]

    @api.model
    def _force_storage_limit(self, limit=100):
        """
        Migrate up to `limit` attachments into the current storage.
        Then garbage‐collect any local S3 cache files older than 1 hour.
        """
        domain = expression.AND([
            self._get_storage_domain(),
            # only binary attachments
            ['&', ('type', '=', 'binary'),
             '|', ('res_field', '=', False), ('res_field', '!=', False)]
        ])
        to_migrate = self.search(domain, limit=limit)
        if not to_migrate:
            _logger.info("No attachments to migrate into '%s' storage.", self._storage())
            return

        _logger.info("Migrating %d attachments into '%s' storage", len(to_migrate), self._storage())
        for attach in to_migrate:
            # Use your _move_content logic; adapt if you named it differently:
            attach.with_context(attachment_storage=self._storage())._move_content(self._storage())

        # Clean up the S3 cache of any files older than 1 hour
        self._s3_cache_gc(hours=1)

    @api.model
    def _s3_cache_gc(self, hours=-24):
        """
        Delete local files in the S3 cache folder older than `hours` hours.
        Default -24 = delete anything older than 24h.
        """
        from_timestamp = time.time() + hours * 3600
        cache_dir = self._s3_cache()  # your method that returns the local cache path
        if not os.path.isdir(cache_dir):
            return

        count = defaultdict(int)
        for root, dirs, files in os.walk(cache_dir):
            for fname in files:
                full = os.path.join(root, fname)
                if os.path.getmtime(full) < from_timestamp:
                    try:
                        os.unlink(full)
                        count['file'] += 1
                    except OSError:
                        _logger.warning("Could not delete cache file %s", full)
            for dname in dirs:
                dpath = os.path.join(root, dname)
                if not os.listdir(dpath):
                    try:
                        shutil.rmtree(dpath)
                        count['dir'] += 1
                    except OSError:
                        _logger.warning("Could not delete cache dir %s", dpath)

        _logger.info("S3 cache GC: deleted %d files and %d dirs", count['file'], count['dir'])

    @api.model
    def _s3_cache(self):
        return config.get("s3_cache_dir") or os.path.join(config['data_dir'], 's3_cache')

    @api.model
    def _s3_cache_file(self, s3_key):
        return os.path.join(self._s3_cache(), *s3_key.split('/'))

    def _register_hook(self):
        super(IrAttachment, self)._register_hook()
        patch_http_stream()


# ADDITIONAL FIX: Override the web content controller if needed
from odoo import http
from odoo.http import request
import requests


class IrHttpS3Presigned(http.Controller):

    @http.route(['/web/content/<int:id>'], type='http', auth='public', methods=['GET'])
    def content_attachment_by_id(self, id, **kwargs):
        """Override content route to handle S3 presigned URLs"""
        try:
            attachment = request.env['ir.attachment'].sudo().browse(id)

            if not attachment.exists():
                return request.env['ir.http']._get_serve_attachment()

            if attachment._is_static_asset():
                return request.env['ir.http']._get_serve_attachment()

            print("TYPE", attachment.mimetype)
            if attachment.mimetype in [
                'text/css',
                'application/javascript',
                'application/x-javascript',
                'application/font-woff',
                'application/font-woff2',
                'font/woff',
                'font/woff2'
            ]:
                return request.env['ir.http']._get_serve_attachment()

            if attachment.s3_key:
                # For S3 attachments, redirect to presigned URL
                presigned_url = attachment._get_presigned_url()
                print(presigned_url)
                if presigned_url:
                    s3_response = requests.get(presigned_url, stream=True)
                    if s3_response.status_code == 200:
                        headers = {
                            'Content-Type': s3_response.headers.get('Content-Type', 'application/octet-stream'),
                            'Content-Disposition': s3_response.headers.get('Content-Disposition'),
                            'Access-Control-Allow-Origin': 'http://localhost:8069',
                            'Access-Control-Allow-Methods': 'GET, OPTIONS',
                            'Access-Control-Allow-Headers': 'Content-Type',
                        }
                        return Response(s3_response.content, headers=headers)

                    else:
                        _logger.error(f"S3 returned {s3_response.status_code} for attachment {id}")
                else:
                    _logger.error(f"Failed to generate presigned URL for attachment {id}")

        except Exception as e:
            _logger.exception(f"Error while serving attachment {id} from S3: {e}")

        # Fallback to default behavior
        return request.env['ir.http']._get_serve_attachment()

    # @http.route([
    #     '/web/image/<string:model>/<int:res_id>/<string:field>',
    #     '/web/image/<string:model>/<int:res_id>/<string:field>/<string:filename>'
    # ], type='http', auth='public')
    # def s3_image(self, model, res_id, field, filename=None, **kwargs):
    #     # 1) Try to find the backing attachment
    #     Attachment = request.env['ir.attachment'].sudo()
    #     attach = Attachment.search([
    #         ('res_model', '=', model),
    #         ('res_id', '=', res_id),
    #         ('res_field', '=', field),
    #         ('s3_key', '!=', False),
    #     ], limit=1)
    #     print("attach", attach)
    #
    #     if attach:
    #         # 2) Get presigned URL and stream or redirect
    #         url = attach._get_presigned_url()
    #         print("urllss cont", url)
    #         if url:
    #             # Option A: Redirect browser to S3 (fastest)
    #             return http.redirect_with_hash(url)
    #             # Option B: Proxy through Odoo
    #             # s3r = requests.get(url, stream=True)
    #             # headers = {
    #             #     'Content-Type': s3r.headers.get('Content-Type'),
    #             #     'Cache-Control': s3r.headers.get('Cache-Control'),
    #             #     # (Optionally add CORS, security headers, etc.)
    #             # }
    #             # return Response(s3r.content, headers=headers)
    #
    #     # 3) Fallback to default
    #     return request.env['ir.http']._get_serve_attachment(
    #         model, res_id, field, **kwargs
    #     )

    # @http.route([
    #     '/web/image/<string:model>/<int:res_id>/<string:field>',
    #     '/web/image/<string:model>/<int:res_id>/<string:field>/<string:filename>'
    # ], type='http', auth='public')
    # def s3_image(self, model, res_id, field, filename=None, **kwargs):
    #     """Handle S3 image serving"""
    #     Attachment = request.env['ir.attachment'].sudo()
    #     print("Helo")
    #     attach = Attachment.search([
    #         ('res_model', '=', model),
    #         ('res_id', '=', res_id),
    #         ('res_field', '=', field),
    #         ('s3_key', '!=', False),
    #     ], limit=1)
    #     print("Helo Hello",attach)
    #     if attach:
    #         print("Here inside attache controller")
    #         # For image fields, serve the image directly
    #         if field in ['image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 'avatar_1920',
    #                      'avatar_1024', 'avatar_512', 'avatar_256', 'avatar_128']:
    #             try:
    #                 image_data = attach._s3_read_binary(attach.s3_key)
    #                 if image_data:
    #
    #                     headers = {
    #                         'Content-Type': attach.mimetype or 'image/jpeg',
    #                         'Cache-Control': 'max-age=3600',
    #                         'Access-Control-Allow-Origin': '*',
    #                     }
    #                     return Response(image_data, headers=headers)
    #             except Exception as e:
    #                 _logger.error(f"Failed to serve S3 image {attach.id}: {e}")
    #
    #         # For non-image fields, use presigned URL
    #         url = attach._get_presigned_url()
    #         if url:
    #             return http.redirect_with_hash(url)
    #
    #     # Fallback: get directly from the model (for computed image fields)
    #     try:
    #         record = request.env[model].sudo().browse(res_id)
    #         image_data = record[field]  # works even for computed fields
    #
    #         if image_data:
    #             headers = [
    #                 ('Content-Type', 'image/jpeg'),
    #                 ('Content-Length', str(len(image_data))),
    #                 ('Cache-Control', 'max-age=3600'),
    #                 ('Access-Control-Allow-Origin', '*'),
    #             ]
    #             return Response(image_data, headers=headers)
    #     except Exception as e:
    #         _logger.error(f"[S3 Fallback] Failed to fetch field {field} from {model}({res_id}): {e}")
    #
    #     return Response(status=404)