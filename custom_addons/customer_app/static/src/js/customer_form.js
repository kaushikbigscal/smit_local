
/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.WebsiteCustomerContactRequestForm = publicWidget.Widget.extend({
    selector: ".customer_form",

    start: function () {
        const $selects = this.$('.select_box_test');
        const $complaintSelect = this.$('#complaint-select');
        const $reasonSelect = this.$('#reason-code-select');

        // Initialize select2 on all relevant select boxes
        if ($selects.length && $.fn.select2) {
            $selects.select2({
                width: '100%',
                placeholder: 'Select Complaint Type',
                allowClear: true,
            });
        }

        // Exit early if elements not found
        if (!$complaintSelect.length || !$reasonSelect.length) {
            console.warn("complaint-select or reason-code-select not found.");
            return this._super.apply(this, arguments);
        }

        console.log("Select2 initialized and selects found.");

        // Event binding for complaint type selection
        $complaintSelect.on('change', () => {
            const selectedOptions = $complaintSelect.val() || [];
            console.log("Selected complaint types:", selectedOptions);

            const selectedNames = [];

            $complaintSelect.find('option:selected').each(function () {
                selectedNames.push($(this).text().trim());
            });

            console.log("Selected Complaint Type Names:", selectedNames);


            // Clear existing reason code options
            $reasonSelect.empty();

            if (!selectedOptions.length) {
                $reasonSelect.append(`<option value="">Select Complaint Type First</option>`);
                if ($reasonSelect.hasClass('select2-hidden-accessible')) {
                    $reasonSelect.trigger('change.select2');
                }
                return;
            }

            const selectedIds = selectedOptions.map(Number);
            console.log("Sending to controller:", { complaint_types: selectedIds });

            // Send AJAX request to backend
            fetch('/get/reason/by/complaint', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                    body: JSON.stringify({ complaint_type_names: selectedNames }),

            })
            .then(res => res.json())
            .then(data => {
                const reasonCodes = (data?.reason_codes) || [];
                console.log("Received reason codes:", reasonCodes);

                if (!reasonCodes.length) {
                    $reasonSelect.append(`<option value="">No matching reason codes</option>`);
                } else {
//                    $reasonSelect.append(`<option value="">Select Reason Code...</option>`);
                    reasonCodes.forEach(reason => {
                        $reasonSelect.append(
                            $('<option>', {
                                value: reason.id,
                                text: reason.name,
                            })
                        );
                    });
                }

                // Refresh Select2 if needed
                if ($reasonSelect.hasClass('select2-hidden-accessible')) {
                    $reasonSelect.trigger('change.select2');
                }
            })
            .catch(err => {
                console.error('Error fetching reason codes:', err);
                $reasonSelect.append(`<option value="">Error loading reason codes</option>`);
            });
        });

        return this._super.apply(this, arguments);
    },
});
