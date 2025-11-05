/** @odoo-module */

import {
    deserializeDate,
    deserializeDateTime,
    parseDate,
    parseDateTime,
} from "@web/core/l10n/dates";
import PublicWidget from "@web/legacy/js/public/public_widget";

export const DateTimePickerWidget = PublicWidget.Widget.extend({
    selector: "[data-widget='datetime-picker']",
    start() {
        this._super(...arguments);
        const { widgetType, minDate, maxDate } = this.el.dataset;
        const type = widgetType || "datetime";
        const { value } = this.el;
        const [parse, deserialize] =
            type === "date" ? [parseDate, deserializeDate] : [parseDateTime, deserializeDateTime];

        // Create picker
        this.disable = this.call("datetime_picker", "create", {
            target: this.el,
            pickerProps: {
                type,
                minDate: minDate && deserialize(minDate),
                maxDate: maxDate && deserialize(maxDate),
                value: parse(value),
            },
        }).enable();

        // Delegated click handler to catch the dynamically inserted picker buttons
        this._onDocumentClick = (ev) => {
            // Find nearest button inside the picker popup
            const btn = ev.target.closest(".datetimepicker .btn, .o_datetime_picker .btn");
            if (!btn) return;

            // We only want the "Close" style button (secondary). Adjust logic if your template differs.
            if (!btn.classList.contains("btn-secondary")) return;

            // Defer clearing so we run after the picker's internal handlers (which may apply the value).
            setTimeout(() => {
                // Option A: clear completely
                this.el.value = "";
                // Option B (if you want to restore a previous value instead of empty):
                // this.el.value = this._originalValue || "";
                // Notify listeners that the input changed
                this.el.dispatchEvent(new Event("input", { bubbles: true }));
                this.el.dispatchEvent(new Event("change", { bubbles: true }));
            }, 0);
        };

        document.addEventListener("click", this._onDocumentClick);
    },

    destroy() {
        if (this._onDocumentClick) {
            document.removeEventListener("click", this._onDocumentClick);
            this._onDocumentClick = null;
        }
        if (this.disable) {
            this.disable();
        }
        return this._super(...arguments);
    },
});

PublicWidget.registry.DateTimePickerWidget = DateTimePickerWidget;
