odoo.define('customer_app.portal_pay_now', [], function (require) {
    "use strict";

    console.log("Portal pay_now JS loaded...");

    // Use setTimeout to ensure DOM exists
    setTimeout(() => {
        document.querySelectorAll("a[data-bs-target='#pay_with']").forEach(btn => {
            btn.addEventListener("click", function () {
                const modalId = this.getAttribute('data-bs-target');
                console.log("modal id:", modalId);

                const modalEl = document.querySelector(modalId);
                console.log("modal element:", modalEl);

                if (modalEl) {
                    const dueInput = modalEl.querySelector("#due_amount");
                    console.log("due input:", dueInput);

                    if (dueInput) {
                        const dueAmount = this.dataset.dueAmount || "0.00";
                        dueInput.value = dueAmount;
                        dueInput.dataset.invoiceId = this.dataset.invoiceId;
                        console.log("due amount set:", dueAmount);
                    }
                }
            });
        });
    }, 2000); // wait 2 seconds to ensure portal content loaded
});
