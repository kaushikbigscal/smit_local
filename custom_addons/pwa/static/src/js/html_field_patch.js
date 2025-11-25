/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { HtmlField } from "@web_editor/js/backend/html_field";


// Save original setup method before patching
const originalSetup = HtmlField.prototype.setup;

patch(HtmlField.prototype, {
    setup() {
        // Call original setup
        originalSetup.call(this);


        if (window.innerWidth <= 768) {

            // Use setTimeout to ensure DOM is ready
            setTimeout(() => {
                this.setupMobileToolbarBehavior();
            }, 100);
        }
    },

    setupMobileToolbarBehavior() {

        // Find all possible toolbar selectors
        const toolbarSelectors = [
            '#toolbar',
            '.note-toolbar',
            '.o_field_html_toolbar',
            '.note-editor .note-toolbar',
            '[class*="toolbar"]'
        ];

        let toolbar = null;
        for (const selector of toolbarSelectors) {
            toolbar = document.querySelector(selector);
            if (toolbar) {
                break;
            }
        }

        if (!toolbar) {
            setTimeout(() => this.setupMobileToolbarBehavior(), 500);
            return;
        }

        // Hide toolbar initially on mobile
        toolbar.style.display = "none";

        // Find HTML field editable areas
        const editableSelectors = [
            '.note-editable',
            '[contenteditable="true"]',
            '.o_field_html textarea',
            '.o_field_html input'
        ];

        let editableAreas = [];
        for (const selector of editableSelectors) {
            const elements = document.querySelectorAll(selector);
            editableAreas = editableAreas.concat(Array.from(elements));
        }

        if (editableAreas.length === 0) {
            setTimeout(() => this.setupMobileToolbarBehavior(), 500);
            return;
        }

        // Add event listeners to all HTML field editable areas
        editableAreas.forEach((editableArea, index) => {
            // Show toolbar when any HTML field gains focus
            const focusHandler = () => {
                toolbar.style.display = "block";
            };

            // Hide toolbar when HTML field loses focus
            const blurHandler = () => {
                // Small delay to check if focus moved to another HTML field
                setTimeout(() => {
                    const activeElement = document.activeElement;
                    const isHtmlField = editableAreas.some(area =>
                        area === activeElement || area.contains(activeElement)
                    );

                    if (!isHtmlField) {
                        toolbar.style.display = "none";
                    }
                }, 50);
            };

            editableArea.addEventListener('focus', focusHandler);
            editableArea.addEventListener('blur', blurHandler);
            editableArea.addEventListener('click', focusHandler);
        });

    },
});





///** @odoo-module **/
//import { patch } from "@web/core/utils/patch";
//import { HtmlField } from "@web_editor/js/backend/html_field";
//
//console.log("📦 mobile html_field_patch.js loaded");
//
//// Save original setup method before patching
//const originalSetup = HtmlField.prototype.setup;
//
//patch(HtmlField.prototype, {
//    setup() {
//        // Call original setup
//        originalSetup.call(this);
//
//        console.log("📌 HtmlField patch setup() called");
//
//        if (window.innerWidth <= 768) {
//            console.log("📱 Mobile mode detected");
//
//            const toolbar = document.getElementById("toolbar");
//            if (toolbar) {
//                console.log("🔍 Toolbar found, hiding it now...");
//                toolbar.style.display = "none";
//            } else {
//                console.log("⚠️ Toolbar not found in DOM yet, retrying...");
//
//                // Retry a bit later in case it's loaded asynchronously
//                setTimeout(() => {
//                    const lateToolbar = document.getElementById("toolbar");
//                    if (lateToolbar) {
//                        console.log("✅ Toolbar found after delay, hiding it...");
//                        lateToolbar.style.display = "none";
//                    } else {
//                        console.log("❌ Still no toolbar found");
//                    }
//                }, 500);
//            }
//        }
//    },
//});
