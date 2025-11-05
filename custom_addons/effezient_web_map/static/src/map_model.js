/** @odoo-module **/

export class MapModel {
    async load(params) {
        const { resModel, context, limit, offset, fieldNames, domain, order } = params;

        // Fallback RPC logic (you could improve this by using ORM service if needed)
        const result = await this.env.services.rpc({
            model: resModel,
            method: "search_read",
            args: [domain || [], fieldNames],
            kwargs: { limit, offset, context, order },
        });

        return {
            records: result,
            limit,
            offset,
            domain,
            context,
            resModel,
        };
    }
}
