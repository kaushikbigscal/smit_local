/** @odoo-module **/

import { Chatter } from "@mail/core/web/chatter";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    get normalAttachments() {
        const modelName = this.env.model?.root?.resModel;

        let raw = this.state.thread?.attachments || [];
        if (!Array.isArray(raw) && raw.models) {
            raw = raw.models;
        }

        if (modelName === "sale.order") {
            return raw.filter(att => !att.name?.startsWith("Checklist -"));
        } else {
            return raw;
        }
    },

    get checklistAttachments() {
        const modelName = this.env.model?.root?.resModel;

        if (modelName !== "sale.order") {
            return [];
        }

        let raw = this.state.thread?.attachments || [];
        if (!Array.isArray(raw) && raw.models) {
            raw = raw.models;
        }

        return raw.filter(att => att.name?.startsWith("Checklist -"));
    },
});





///** @odoo-module **/
//
//import { Chatter } from "@mail/core/web/chatter";
//import { patch } from "@web/core/utils/patch";
//
//console.log("✅ chatter_checklist_patch.js loaded");
//
//patch(Chatter.prototype, {
//    get normalAttachments() {
//        console.log("normalAttachments getter called");
//        let raw = this.state.thread?.attachments || [];
//        // if it's not an array, try .models
//        if (!Array.isArray(raw) && raw.models) {
//            console.log("attachments is RecordSet, using .models");
//            raw = raw.models;
//        }
//        console.log("attachments before filter:", raw);
//        return raw.filter(att => !att.name?.startsWith("Checklist -"));
//    },
//
//    get checklistAttachments() {
//        console.log("checklistAttachments getter called");
//        let raw = this.state.thread?.attachments || [];
//        if (!Array.isArray(raw) && raw.models) {
//            console.log("attachments is RecordSet, using .models");
//            raw = raw.models;
//        }
//        const checklist = raw.filter(
//            att => att.name && att.name.startsWith("Checklist -")
//        );
//        console.log("Checklist attachments found:", checklist);
//        return checklist;
//    },
//});