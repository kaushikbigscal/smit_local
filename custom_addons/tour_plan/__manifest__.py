
{
    "name": "Tour Plan",
    "version": "17.0.1.0.0",
    "development_status": "Beta",
    "category": "Customer Relationship Management",
    "author": "Mukesh",
    "license": "AGPL-3",
    "depends": ["crm", "calendar"],
    "data": [
        "data/crm_salesperson_planner_sequence.xml",
        "wizards/crm_salesperson_planner_visit_close_wiz_view.xml",
        "wizards/crm_salesperson_planner_visit_template_create.xml",
        "views/crm_salesperson_planner_visit_views.xml",
        "views/crm_salesperson_planner_visit_close_reason_views.xml",
        "views/crm_salesperson_planner_visit_template_views.xml",
        "views/crm_salesperson_planner_menu.xml",
        "views/res_partner.xml",
        "views/crm_lead.xml",
        "data/ir_cron_data.xml",
        "security/crm_salesperson_planner_security.xml",
        "security/ir.model.access.csv",
        "views/visit_timer_tracking.xml",
        "views/res_config_settings_views.xml",
        "views/visit_objective_tags_views.xml",
        "views/state_city_views.xml",
        "views/city_zip_views.xml"
    ],

    "installable": True,
}
