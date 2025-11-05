{
    "name": "Barcode Container",
    "version": "17.0.1.0.0",
    "category": "Inventory/Barcode",
    "summary": "Manage containers, species lines and QR code scanning",
    "description": """
Custom Container & Species Management
-------------------------------------
- Manage containers with multiple species lines
- Auto sequence for Packing List Number
- QR Code printing for each line
- 4x6 inch label PDF generation
- Mobile QR scanner widget (camera-based)
    """,
    "author": "smit",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "stock",
        "web",
        "portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "report/container_report.xml",
        "report/line_qr_code.xml",
        "views/container_views.xml",
        "views/menu.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "barcode_container/static/src/js/qr_scanner_action.js",
            "barcode_container/static/src/js/qr_scanner_dialog.js",
            "barcode_container/static/src/xml/qr_scanner_template.xml",
            "barcode_container/static/src/css/qr_scanner_styles.css",
            # CDN for jsQR.
            "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js",
        ],
    },
    "application": True,
    "installable": True,
}
