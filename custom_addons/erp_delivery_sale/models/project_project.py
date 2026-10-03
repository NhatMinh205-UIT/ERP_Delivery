from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # NOTE: named `erp_sale_order_id`, not the plain `sale_order_id` used in
    # the execution plan's code sketch. Odoo 18 ships a separate standard
    # addon `sale_project` (auto_install when both `sale_management` and
    # `project_account` happen to be installed together — e.g. once
    # Invoicing is added to a stack that already has Sales+Project) which
    # defines its OWN `project.project.sale_order_id` (a related, non-unique
    # field with completely different semantics: `related='sale_line_id.
    # order_id'`). `erp_delivery_sale` does not depend on `sale_project`, so
    # there is no hard conflict today, but two different modules defining
    # the same field name differently on the same model is exactly the kind
    # of fragile, instance-dependent collision this addon must not risk —
    # see docs/implementation/004_go_live_base_and_sales_integration.md,
    # Technical Decisions.
    erp_sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Source Sale Order",
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        (
            "erp_sale_order_id_uniq",
            "UNIQUE(erp_sale_order_id)",
            "A Sale Order can only generate one ERP project.",
        ),
    ]

    def action_view_erp_source_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.erp_sale_order_id.id,
            "view_mode": "form",
        }
