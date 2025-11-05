/** @odoo-module **/

export class MapArchParser {
    parse(arch) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(arch, "text/xml");
        const fields = Array.from(xmlDoc.getElementsByTagName("field"));

        const fieldNames = fields.map(field => field.getAttribute("name"));

        return {
            defaultOrder: xmlDoc.documentElement.getAttribute("default_order") || "",
            panelTitle: xmlDoc.documentElement.getAttribute("string") || "Map Items",
            fieldNames,
            fieldNamesMarkerPopup: fieldNames.map(name => ({
                fieldName: name,
                string: name,
            })),
            hideAddress: xmlDoc.documentElement.getAttribute("hide_address") === "true",
            hideName: xmlDoc.documentElement.getAttribute("hide_name") === "true",
            hideTitle: xmlDoc.documentElement.getAttribute("hide_title") === "true",
            routing: xmlDoc.documentElement.getAttribute("routing") === "true",
            limit: parseInt(xmlDoc.documentElement.getAttribute("limit") || "80"),
            resPartnerField: xmlDoc.documentElement.getAttribute("res_partner_field") || "partner_id",
        };
    }
}
