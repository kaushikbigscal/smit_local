/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";


publicWidget.registry.TableSortWidget = publicWidget.Widget.extend({
    selector: ".o_portal_my_doc_table",
    start: function () {


        const table = this.el;
        const headers = table.querySelectorAll("th.sortable");
        if (!headers.length) {
            console.warn("No sortable headers found.");
            return;
        }

        let direction = 1;
        let activeColumn = null;

        headers.forEach((header, index) => {
            header.style.cursor = "pointer";
            header.addEventListener("click", () => {

                const tbody = table.querySelector("tbody");
                if (!tbody) return;

                const rows = Array.from(tbody.querySelectorAll("tr"));
                if (activeColumn === index) {
                    direction *= -1;
                } else {
                    direction = 1;
                    activeColumn = index;
                }

                rows.sort((a, b) => {
                    const aText = a.children[index]?.textContent?.trim().toLowerCase() || "";
                    const bText = b.children[index]?.textContent?.trim().toLowerCase() || "";
                    return aText.localeCompare(bText) * direction;
                });

                tbody.innerHTML = "";
                rows.forEach(row => tbody.appendChild(row));

                // Update sort icons
                headers.forEach((h, i) => {
                    const icon = h.querySelector("i");
                    if (icon) {
                        icon.className = "fa fa-sort ms-1";
                        if (i === index) {
                            icon.className = direction === 1
                              ? "fa fa-arrow-up ms-1"
                              : "fa fa-arrow-down ms-1";
                            icon.style.color = "blue";
                        }
                    }
                });
            });
        });
        return this._super(...arguments);
    }
});
