/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

class FSMFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {


            const btnShow = document.querySelector("#toggle_more_options_btn_show");
            const btnHide = document.querySelector("#toggle_more_options_btn_hide");
            const section = document.querySelector("#more_options_section");

            if (btnShow && btnHide && section) {
                btnShow.addEventListener("click", () => {
                    section.style.display = "block";
                    btnShow.style.display = "none";
                });

                btnHide.addEventListener("click", () => {
                    section.style.display = "none";
                    btnShow.style.display = "block";
                });

                // Initial state
                section.style.display = "none";
                btnShow.style.display = "block";
                btnHide.style.display = "block"; // always visible inside the section
            } else {
                console.warn("Some elements are missing in the DOM.");
            }
        });
    }
}

registry.category("views").add("fsm_toggle_form", {
    ...registry.category("views").get("form"),
    Controller: FSMFormController,
});









