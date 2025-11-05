/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { MapArchParser } from "./map_arch_parser";
import { MapModel } from "./map_model";
import { MapController } from "./map_controller";

import { Component, onMounted, useRef } from "@odoo/owl";

export class GoogleMapRenderer extends Component {
    setup() {
        console.log("GoogleMapRenderer setup");
        this.mapContainerRef = useRef("googleMapContainer");
        onMounted(() => this.initMap());
    }

    async initMap() {
        console.log("initMap called");
        const container = this.mapContainerRef.el;
        if (!container) {
            console.error("Google Map container not found!");
            return;
        }
        const map = new google.maps.Map(container, {
            zoom: 4,
            center: { lat: 22.9734, lng: 78.6569 },
        });

        // Extract partner IDs from records using the resPartnerField
        const records = this.props.modelParams?.records || [];
        console.log("Records:", records);
        const resPartnerField = this.props.modelParams?.resPartnerField || "partner_id";
        const partnerIds = [...new Set(records.map(r => r[resPartnerField]).filter(Boolean))];
        console.log("Partner IDs:", partnerIds);

        const partners = await this.fetchPartners(partnerIds);
        console.log("Partners:", partners);

        partners.forEach(partner => {
            if (partner.partner_latitude && partner.partner_longitude) {
                new google.maps.Marker({
                    position: {
                        lat: partner.partner_latitude,
                        lng: partner.partner_longitude
                    },
                    map,
                    title: partner.name
                });
            }
        });
    }

    async fetchPartners(partnerIds) {
        console.log("Fetching partners for IDs:", partnerIds);
        const result = await this.rpc("/effezient_web_map/partners", { partner_ids: partnerIds });
        return result;
    }

    static template = "CustomerMap";
}

export const mapView = {
    type: "map",
    display_name: _t("Map"),
    icon: "fa fa-map-marker",
    multiRecord: true,
    Controller: MapController,
    Renderer: GoogleMapRenderer,
    Model: MapModel,
    ArchParser: MapArchParser,
//    buttonTemplate: "web_map.MapView.Buttons",

    props: (genericProps, view, config) => {
        let modelParams = genericProps.state;
        if (!modelParams) {
            const { arch, resModel, fields, context } = genericProps;
            const parser = new view.ArchParser();
            const archInfo = parser.parse(arch);
            const views = config.views || [];
            modelParams = {
                context: context,
                defaultOrder: archInfo.defaultOrder,
                fieldNames: archInfo.fieldNames,
                fieldNamesMarkerPopup: archInfo.fieldNamesMarkerPopup,
                fields: fields,
                hasFormView: views.some((view) => view[1] === "form"),
                hideAddress: archInfo.hideAddress || false,
                hideName: archInfo.hideName || false,
                hideTitle: archInfo.hideTitle || false,
                limit: archInfo.limit || 80,
                numbering: archInfo.routing || false,
                offset: 0,
                panelTitle: archInfo.panelTitle || config.getDisplayName() || _t("Items"),
                resModel: resModel,
                resPartnerField: archInfo.resPartnerField,
                routing: archInfo.routing || false,
            };
        }

        return {
            ...genericProps,
            Model: view.Model,
            modelParams,
            Renderer: view.Renderer,
            buttonTemplate: view.buttonTemplate,
        };
    },
};

console.log("Registering custom map view");
registry.category("views").add("map", mapView);



///** @odoo-module */
//
//import { Component, onMounted, useRef } from "@odoo/owl";
//import { registry } from "@web/core/registry";
//
//export class CustomerMap extends Component {
//    setup() {
//        this.mapContainerRef = useRef("googleMapContainer");
//        onMounted(() => this.initMap());
//    }
//
//    async initMap() {
//        const container = this.mapContainerRef.el;
//        const map = new google.maps.Map(container, {
//            zoom: 4,
//            center: { lat: 22.9734, lng: 78.6569 }, // Default: India center
//        });
//
//        const partners = await this.fetchPartners();
//
//        partners.forEach(partner => {
//            if (partner.partner_latitude && partner.partner_longitude) {
//                const marker = new google.maps.Marker({
//                    position: {
//                        lat: partner.partner_latitude,
//                        lng: partner.partner_longitude
//                    },
//                    map,
//                    title: partner.name
//                });
//            }
//        });
//    }
//
//    async fetchPartners() {
//        const result = await this.rpc("/effezient_web_map/partners");
//        return result;
//    }
//
//    static template = "CustomerMap";
//}
//
////registry.category("actions").add("customer_map", CustomerMap);
//registry.category("views").add("map", CustomerMap);