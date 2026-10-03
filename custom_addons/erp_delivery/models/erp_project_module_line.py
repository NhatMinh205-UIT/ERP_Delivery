from odoo import api, fields, models


class ErpProjectModuleLine(models.Model):
    _name = "erp.project.module.line"
    _description = "ERP Project Module Line"
    _order = "project_id, solution_id"

    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    solution_id = fields.Many2one(
        comodel_name="erp.solution",
        required=True,
    )
    planned_effort = fields.Float(help="Planned effort, in hours.")
    actual_effort = fields.Float(
        compute="_compute_actual_effort",
        store=True,
        help="Sum of the manually-entered actual hours of the linked tasks.",
    )
    consultant_id = fields.Many2one(comodel_name="res.users")
    currency_id = fields.Many2one(
        related="project_id.currency_id",
        store=True,
    )
    price = fields.Monetary(currency_field="currency_id")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ],
        default="draft",
    )
    note = fields.Text()
    task_ids = fields.One2many(
        comodel_name="project.task",
        inverse_name="module_line_id",
    )

    _sql_constraints = [
        (
            "project_solution_uniq",
            "UNIQUE(project_id, solution_id)",
            "A solution can only be added once per project.",
        ),
    ]

    @api.depends("task_ids.erp_actual_hours")
    def _compute_actual_effort(self):
        for line in self:
            line.actual_effort = sum(line.task_ids.mapped("erp_actual_hours"))
