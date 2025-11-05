from odoo import models, fields,api,_
from lxml import etree
from odoo.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
import filetype
import io
import base64


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_qr_code_scanner = fields.Boolean("Enable Scanner QR Code/ Barcode",  config_parameter="customer_app.enable_qr_code_scanner")
    enable_customer_portal = fields.Boolean("Enable Customer Portal", config_parameter="customer_app.enable_customer_portal",tracking=True )
    enable_set_banner = fields.Boolean("Enable Set Banner", config_parameter="customer_app.enable_set_banner")
    # image = fields.Binary("Upload Image")
    image = fields.Many2many(
        'ir.attachment',
        'res_company_ir_attachment_rel',  
        'company_id',  
        'attachment_id',  
        string="Images",
        domain="[('res_model', '=', 'res.company')]",
        help="For the best display, please upload images with a width of 900px and height of 300px."
    )

    banner_image_ids = fields.One2many('res.company.banner.image', 'company_id', string="Banner Images")

    @api.constrains('image')
    def _check_image_format(self):
        for record in self:
            if record.enable_set_banner and record.image:
                for attachment in record.image:
                    try:
                        if not attachment.datas:
                            continue
                        img_bytes = base64.b64decode(attachment.datas)
                        kind = filetype.guess(img_bytes)
                        if not kind or kind.extension not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                            raise ValidationError(
                                _("Unsupported image format: %s" % (kind.extension if kind else "unknown")))
                    except Exception as e:
                        raise ValidationError(_("Image validation failed: %s" % str(e)))

    def write(self, vals):
        res = super().write(vals)

        group_portal = self.env.ref('base.group_portal', raise_if_not_found=False)

        for company in self:
            # CASE 1: When customer portal is turned OFF
            if vals.get('enable_customer_portal') is False:
                company.write({
                    'enable_set_banner': False,
                    'image': False,
                    'banner_image_ids': [(5, 0, 0)],  # Clear all banner images
                })

            # CASE 2: When banner flag is turned OFF independently
            if vals.get('enable_set_banner') is False:
                company.write({
                    'image': False,
                    'banner_image_ids': [(5, 0, 0)],
                })

            # Archive/unarchive portal users if the flag is present
            if 'enable_customer_portal' in vals and group_portal:
                portal_users = self.env['res.users'].with_context(active_test=False).search([
                    ('company_ids', 'in', company.id),
                    ('groups_id', 'in', group_portal.id),
                ])
                portal_users.write({'active': vals['enable_customer_portal']})

        self._set_images_public()

        return res

    @api.model
    def create(self, vals):
        company = super().create(vals)
        company._set_images_public()
        return company

    def _set_images_public(self):
        for company in self:
            for attachment in company.image:
                if not attachment.public:
                    print(f"Making Attachment ID {attachment.id} public...")
                    attachment.sudo().write({'public': True})

class ResCompanyBannerImage(models.Model):
    _name = 'res.company.banner.image'
    _description = 'Company Banner Image'

    name = fields.Char("Banner Name")
    image = fields.Binary("Image", required=True, attachment=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)

    def _resize_image_to_container(self, image_b64):
        try:
            img_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(img_bytes))
            resized_image = image.convert('RGB').resize((900, 300), Image.ANTIALIAS)

            buffer = io.BytesIO()
            resized_image.save(buffer, format='JPEG')  # Always save as JPEG
            return base64.b64encode(buffer.getvalue())
        except Exception as e:
            raise ValidationError(_("Image resizing failed: %s") % str(e))

    @api.model
    def create(self, vals):
        if vals.get("image"):
            vals["image"] = self._resize_image_to_container(vals["image"])
        return super().create(vals)

    def write(self, vals):
        if vals.get("image"):
            vals["image"] = self._resize_image_to_container(vals["image"])
        return super().write(vals)

class ResUsers(models.Model):
    _inherit = 'res.users'

    # webpush_subscription = fields.Json("Web Push Subscription")

    def write(self, vals):
        group_portal = self.env.ref('base.group_portal', raise_if_not_found=False)
        if not group_portal:
            return super().write(vals)

        # Detect if Customer Portal group is being assigned
        portal_selected = any(
            key.startswith('sel_groups_') and value == group_portal.id
            for key, value in vals.items()
        )

        if portal_selected:
            for user in self:
                allowed_companies = user.company_ids
                portal_enabled = any(company.enable_customer_portal for company in allowed_companies)

                if not portal_enabled:
                    raise ValidationError(_(
                        f"Cannot set the User Type 'Customer Portal' for user '{user.name}' because their allowed company does not have Customer Portal access enabled."
                    ))

        return super().write(vals)

