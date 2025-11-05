from odoo import models


class IrQWeb(models.AbstractModel):
    _inherit = 'ir.qweb'

    def _get_asset_bundle(self, bundle_name,
                          css=True, js=True,
                          debug_assets=False, rtl=False,
                          assets_params=None):
        print("Called")
        # 1. First bundle call? inject our context
        if not self.env.context.get('asset_bundle'):
            # this returns a new self.env under the extended context
            self = self.with_context(
                asset_bundle=True,
                attachment_storage='db'
            )
            print("Inside QWEB")
        # 2. Delegate to Odoo’s original logic
        return super(IrQWeb, self)._get_asset_bundle(
            bundle_name,
            css=css,
            js=js,
            debug_assets=debug_assets,
            rtl=rtl,
            assets_params=assets_params,
        )
