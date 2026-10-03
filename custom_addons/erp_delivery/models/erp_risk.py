from odoo import fields, models


class ErpRisk(models.Model):
    _name = "erp.risk"
    _description = "ERP Project Risk"
    _inherit = ["mail.thread"]
    _order = "level desc, name"

    name = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    level = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        required=True,
        default="medium",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("open", "Open"),
            ("mitigated", "Mitigated"),
            ("closed", "Closed"),
        ],
        default="open",
        tracking=True,
    )
    owner_id = fields.Many2one(comodel_name="res.users")
    mitigation_plan = fields.Text()
