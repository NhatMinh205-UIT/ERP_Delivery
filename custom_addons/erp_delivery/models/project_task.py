from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    risk_level = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
    )
    progress_weight = fields.Float(default=1.0)
    is_mandatory = fields.Boolean()
    acceptance_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="draft",
    )
    module_line_id = fields.Many2one(
        comodel_name="erp.project.module.line",
        domain="[('project_id', '=', project_id)]",
    )
    # NOTE: Core `project` (without the separate `hr_timesheet` addon) does
    # not provide `effective_hours` or `progress` on project.task — those
    # are added by hr_timesheet, which pulls in the whole HR/timesheet
    # subsystem (hr, analytic, ...). Adding that as a dependency of the core
    # erp_delivery addon would be an undisclosed architecture change (see
    # docs/implementation/003_module_lines_tasks_milestones_risks.md,
    # Technical Decisions). erp_actual_hours is a lightweight manual-entry
    # substitute scoped to this addon, used to aggregate
    # erp.project.module.line.actual_effort.
    erp_actual_hours = fields.Float(string="Actual Hours (ERP)")
