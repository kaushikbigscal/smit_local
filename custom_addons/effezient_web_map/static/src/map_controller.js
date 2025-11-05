/** @odoo-module **/

import { Component } from "@odoo/owl";

export class MapController extends Component {
    setup() {
        console.log("✅ MapController setup");
        console.log("Props:", this.props);
    }
}
// Use a template defined in your XML like: <template id="MapController">
MapController.template = "CustomerMap";