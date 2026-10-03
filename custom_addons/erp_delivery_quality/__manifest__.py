{
    "name": "ERP Delivery - Quality Gate",
    "version": "18.0.1.0.0",
    "category": "Services/Project",
    "summary": "Quality scoring and Go-live gate for ERP Delivery projects",
    "author": "Internal Dev Team",
    "license": "LGPL-3",
    # NOTE: depends only on erp_delivery, NOT erp_delivery_sale — Quality
    # Gate must install and work standalone (execution plan Phần 7 / scenario
    # #6). The optional commercial check when Sales is also installed is
    # done via a runtime field-existence check instead, see
    # models/project_project.py.
    "depends": ["erp_delivery"],
    "data": [
        "security/erp_delivery_quality_security.xml",
        "security/ir.model.access.csv",
        "data/quality_criterion_data.xml",
        "views/project_project_views.xml",
        "views/erp_quality_views.xml",
    ],
}
