from odoo import fields, models


class ErpSolution(models.Model):
    _name = "erp.solution"
    _description = "ERP Solution"
    _inherit = ["mail.thread"]
    _order = "category_id, name"

    code = fields.Char(required=True, tracking=True)
    name = fields.Char(required=True, translate=True, tracking=True)
    description_short = fields.Char(translate=True)
    description_rich = fields.Html(translate=True)
    category_id = fields.Many2one(
        comodel_name="erp.solution.category",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    standard_effort = fields.Float(string="Standard Effort (hours)")
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    service_price = fields.Monetary(
        currency_field="currency_id",
    )
    # NOTE: Odoo 18 does not allow `Monetary` fields to be `company_dependent`
    # (see odoo/fields.py COMPANY_DEPENDENT_FIELDS). We use a plain Float
    # stored per-company and render it with widget="monetary" in the view
    # instead, which gives the same company-scoped amount with currency
    # formatting.
    internal_cost = fields.Float(
        company_dependent=True,
        groups="erp_delivery.group_erp_delivery_manager",
        help="Internal delivery cost, confidential and company-specific.",
    )
    image = fields.Binary(attachment=True)
    document_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Documents",
    )

    _sql_constraints = [
        (
            "code_uniq",
            "UNIQUE(code)",
            "Solution Code must be unique.",
        ),
    ]
