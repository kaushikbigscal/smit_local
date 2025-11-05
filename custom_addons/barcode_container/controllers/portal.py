from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.tools.translate import _


class ContainerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'container_count' in counters:
            partner = request.env.user.partner_id
            Container = request.env['barcode.container']
            values['container_count'] = Container.search_count([
                ('consignee_id', '=', partner.id)
            ]) if partner else 0
        return values

    def _prepare_portal_container_values(self, page=1, sortby=None, search=None, search_in='all', **kw):
        """Prepare values for container portal list view"""
        partner = request.env.user.partner_id
        Container = request.env['barcode.container']

        # Define search inputs
        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in All')},
            'name': {'input': 'name', 'label': _('Packing List')},
            'container_number': {'input': 'container_number', 'label': _('Container Number')},
            'bl_nr': {'input': 'bl_nr', 'label': _('BL Number')},
            'reference_nr': {'input': 'reference_nr', 'label': _('Reference Number')},
        }

        # Define sort options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'date desc'},
            'name': {'label': _('Packing List'), 'order': 'name'},
            'container_number': {'label': _('Container Number'), 'order': 'container_number'},
        }

        if not sortby:
            sortby = 'date'

        # Domain
        domain = [('consignee_id', '=', partner.id)]

        # Apply search
        if search and search_in:
            if search_in == 'all':
                domain += ['|', '|', '|',
                           ('name', 'ilike', search),
                           ('container_number', 'ilike', search),
                           ('bl_nr', 'ilike', search),
                           ('reference_nr', 'ilike', search)]
            else:
                domain += [(search_in, 'ilike', search)]

        # Sorting
        order = searchbar_sortings[sortby]['order']

        # Search containers
        all_containers = Container.search(domain, order=order)

        # Pager
        pager = portal_pager(
            url="/my/containers",
            url_args={'sortby': sortby, 'search_in': search_in, 'search': search},
            total=len(all_containers),
            page=page,
            step=self._items_per_page
        )

        offset = pager['offset']
        containers = all_containers[offset:offset + self._items_per_page]

        return {
            'containers': containers,
            'page_name': 'container',
            'pager': pager,
            'default_url': '/my/containers',
            'searchbar_inputs': searchbar_inputs,  # <-- keep as dict
            'search_in': search_in,
            'search': search,
            'sortings': searchbar_sortings,
            'sortby': sortby,
        }

    @http.route(['/my/containers', '/my/containers/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_containers(self, page=1, sortby=None, search=None, search_in='all', **kw):
        values = self._prepare_portal_container_values(
            page=page,
            sortby=sortby,
            search=search,
            search_in=search_in,
            **kw
        )
        return request.render("barcode_container.portal_my_containers", values)

    @http.route(['/my/container/<int:container_id>'], type='http', auth="user", website=True)
    def portal_container_page(self, container_id, access_token=None, **kw):
        """Container detail page"""
        try:
            container_sudo = self._document_check_access('barcode.container', container_id, access_token)
        except Exception:
            return request.redirect('/my')

        values = {
            'container': container_sudo,
            'page_name': 'container',
        }
        return request.render("barcode_container.portal_container_page", values)
