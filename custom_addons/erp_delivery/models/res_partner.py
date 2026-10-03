from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_erp_customer = fields.Boolean(
        string="Is ERP Customer",
        index=True,
        help="Flags this contact as a customer of an ERP implementation project.",
    )
    erp_code = fields.Char(
        string="ERP Customer Code",
        index=True,
        copy=False,
    )
    erp_tier = fields.Selection(
        selection=[
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
        ],
        string="ERP Tier",
    )
    contract_end_date = fields.Date()
    expected_users = fields.Integer()
    # NOTE: string="ERP Subscription Currency", not the generic "Currency" —
    # when the `account` module is also installed (pulled in by a fuller
    # Sales/Invoicing stack; observed in practice while testing the 4
    # install combinations for Sprint 5), it defines its own res.partner
    # field also labeled "Currency", and Odoo logs a duplicate-label
    # warning at registry load. A more specific label avoids it.
    company_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="ERP Subscription Currency",
        compute="_compute_company_currency_id",
        help="Technical field used to display subscription_value in the current company's currency.",
    )
    subscription_value = fields.Monetary(
        currency_field="company_currency_id",
        groups="erp_delivery.group_erp_delivery_manager",
    )
    erp_project_ids = fields.One2many(
        comodel_name="project.project",
        inverse_name="partner_id",
        string="ERP Delivery Projects",
        domain=[("is_erp_delivery", "=", True)],
    )

    _sql_constraints = [
        (
            "erp_code_company_uniq",
            "UNIQUE(erp_code, company_id)",
            "ERP Customer Code must be unique per company.",
        ),
    ]

    @api.depends_context("company")
    def _compute_company_currency_id(self):
        currency = self.env.company.currency_id
        for partner in self:
            partner.company_currency_id = currency
