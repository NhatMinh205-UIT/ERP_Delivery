from odoo import fields, models


class ErpQualityCriterion(models.Model):
    _name = "erp.quality.criterion"
    _description = "ERP Quality Criterion"
    _order = "category, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    weight = fields.Float(default=1.0)
    category = fields.Selection(
        selection=[
            ("task", "Task"),
            ("milestone", "Milestone"),
            ("risk", "Risk"),
            ("commercial", "Commercial"),
        ],
        required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "code_uniq",
            "UNIQUE(code)",
            "Quality Criterion Code must be unique.",
        ),
    ]
