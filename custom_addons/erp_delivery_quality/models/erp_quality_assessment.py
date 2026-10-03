from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ErpQualityAssessment(models.Model):
    _name = "erp.quality.assessment"
    _description = "ERP Quality Assessment"
    _inherit = ["mail.thread"]
    _order = "project_id, criterion_id"

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    criterion_id = fields.Many2one(
        comodel_name="erp.quality.criterion",
        required=True,
        tracking=True,
    )
    score = fields.Float(tracking=True, help="Score from 0 to 10.")
    note = fields.Text()
    assessed_by = fields.Many2one(
        comodel_name="res.users",
        default=lambda self: self.env.user,
    )
    assessed_date = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        (
            "project_criterion_uniq",
            "UNIQUE(project_id, criterion_id)",
            "A criterion can only be assessed once per project.",
        ),
    ]

    @api.constrains("score")
    def _check_score_range(self):
        for assessment in self:
            if not 0 <= assessment.score <= 10:
                raise ValidationError(self.env._("Score must be between 0 and 10."))
