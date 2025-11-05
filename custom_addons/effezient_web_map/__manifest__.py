# -*- coding: utf-8 -*-
{
    "name": "Effezient Web Google Map",
    "version": "1.0",
    "summary": "Display customers on Google Maps",
    "depends": ["base", "web", "contacts"],
    "data": [
        "views/map_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "effezient_web_map/static/src/map_model.js",
            "effezient_web_map/static/src/map_controller.js",
            "effezient_web_map/static/src/map_arch_parser.js",
            "effezient_web_map/static/src/google_map_renderer.js",
            "effezient_web_map/static/src/map_templates.xml",
        ]
    },
    "installable": True,
}
