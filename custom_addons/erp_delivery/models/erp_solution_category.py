from odoo import fields, models


class ErpSolutionCategory(models.Model):
    _name = "erp.solution.category"
    _description = "ERP Solution Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "code_uniq",
            "UNIQUE(code)",
            "Solution Category Code must be unique.",
        ),
    ]
