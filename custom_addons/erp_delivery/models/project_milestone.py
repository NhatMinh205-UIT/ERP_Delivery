from odoo import fields, models


class ProjectMilestone(models.Model):
    # NOTE: Odoo 18's core `project` module already ships `project.milestone`
    # (name, project_id, deadline, is_reached, task_ids, ...). The execution
    # plan calls for a new `erp.milestone` model, but that would duplicate an
    # existing standard object — against the same "reuse the standard object"
    # principle the plan itself applies to project.project/project.task (see
    # execution plan 1.5/1.6). We extend the standard model instead and only
    # add the fields it is missing (is_mandatory, a pending/done/blocked
    # state, and a dedicated note field). See
    # docs/implementation/003_module_lines_tasks_milestones_risks.md.
    _inherit = "project.milestone"

    is_mandatory = fields.Boolean()
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("done", "Done"),
            ("blocked", "Blocked"),
        ],
        default="pending",
    )
    note = fields.Text()
