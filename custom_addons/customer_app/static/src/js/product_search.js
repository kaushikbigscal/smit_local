/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ProductSearchWidget = publicWidget.Widget.extend({
    selector: ".js-product-search-wrapper",
    events: {
        "keyup .js-product-search": "_onKeyup",
        "focusout .js-product-search": "_onFocusOut",
    },

    _onKeyup: function (ev) {
        const query = ev.currentTarget.value.trim();
        const $results = this.$(".js-search-results");

        if (query.length < 2) {
            $results.hide();
            return;
        }

        $.ajax({
            url: "/product/autocomplete",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ jsonrpc: "2.0", method: "call", params: { search_term: query } }),
            dataType: "json",
            success: function (response) {
                const products = response.result || [];
                if (!products.length) return $results.hide();

                const html = products.map((p) => `
                    <li class="dropdown-item d-flex align-items-center" data-url="${p.url}" style="cursor:pointer;">
                        <img src="${p.image_url}" class="me-2 rounded" style="width: 30px; height: 30px;" />
                        <span>${p.name}</span>
                    </li>
                `).join("");

                $results.html(html).show();
            },
        });
    },

    _onFocusOut: function () {
        setTimeout(() => this.$(".js-search-results").hide(), 200);
    },

    start: function () {
        this.$(".js-search-results").on("click", "li", function () {
            const url = $(this).data("url");
            if (url) window.location.href = url;
        });
        return this._super(...arguments);
    },
});
