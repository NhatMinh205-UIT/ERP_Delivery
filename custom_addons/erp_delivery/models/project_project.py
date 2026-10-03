from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

HEALTH_RED_GAP = 20.0
HEALTH_AMBER_GAP = 10.0
HEALTH_AMBER_MAX_OVERDUE_TASKS = 2


class ProjectProject(models.Model):
    _inherit = "project.project"

    is_erp_delivery = fields.Boolean(
        index=True,
        help="Flags this project as an ERP implementation delivery project "
        "managed by the ERP Delivery suite.",
    )
    code = fields.Char(
        index=True,
        readonly=True,
        copy=False,
        help="Auto-generated from sequence erp.project.code when the project is created as an ERP delivery project.",
    )
    # NOTE: `user_id` (standard project.project field, labeled "Project
    # Manager", already tracking=True) is reused as the ERP Project Manager
    # instead of adding a parallel `pm_id` field as literally named in the
    # execution plan — see docs/implementation/002_project_core_workflow.md
    # Technical Decisions for the rationale (avoids a duplicate field with
    # identical semantics, per master prompt 4.4 "no superfluous fields").
    member_ids = fields.Many2many(
        comodel_name="res.users",
        relation="erp_project_member_rel",
        column1="project_id",
        column2="user_id",
        string="Team Members",
    )
    # NOTE: `date_start` (standard field, "Start Date") is reused as-is for
    # the ERP project start date. `planned_go_live` is a new dedicated field
    # rather than reusing the standard `date` ("Expiration Date") field:
    # `date` already carries project-module-specific behavior (daterange
    # widget paired with date_start, special handling in create()) that is
    # unrelated to ERP go-live semantics, so overloading it risks side
    # effects on the shared project.project model.
    planned_go_live = fields.Date(tracking=True, index=True)
    actual_go_live = fields.Date(readonly=True, copy=False, tracking=True)
    # currency_id already exists on project.project (computed from company),
    # reused here as the currency_field for contract_value.
    contract_value = fields.Monetary(
        currency_field="currency_id",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("analysis", "Analysis"),
            ("implementation", "Implementation"),
            ("uat", "UAT"),
            ("ready", "Ready for Go-Live"),
            ("go_live", "Go-Live"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        copy=False,
        tracking=True,
        index=True,
    )
    note_internal = fields.Text(groups="erp_delivery.group_erp_delivery_manager")

    # Sprint 5B performance audit: index the fields actually used in default
    # filters/record rules/search (plan mục 2.5.3/Sprint5B point 4).
    # `partner_id` and `user_id` are standard project.project fields without
    # an index in core; re-declaring just `index=True` here adds the index
    # without redefining the rest of the field (standard Odoo pattern for
    # adding an attribute to an inherited field).
    partner_id = fields.Many2one(index=True)
    user_id = fields.Many2one(index=True)

    module_line_ids = fields.One2many(
        comodel_name="erp.project.module.line",
        inverse_name="project_id",
    )
    risk_ids = fields.One2many(
        comodel_name="erp.risk",
        inverse_name="project_id",
    )
    # milestone_ids: project.milestone already has inverse_name='project_id'
    # (standard field from the `project` module); not redefined here.

    module_count = fields.Integer(
        compute="_compute_module_count",
        store=True,
    )
    total_planned_effort = fields.Float(
        compute="_compute_effort_totals",
        store=True,
    )
    total_actual_effort = fields.Float(
        compute="_compute_effort_totals",
        store=True,
    )
    mandatory_task_count = fields.Integer(
        compute="_compute_mandatory_task_counts",
        store=True,
    )
    mandatory_done_count = fields.Integer(
        compute="_compute_mandatory_task_counts",
        store=True,
    )
    # NOTE: core `project` (without the `hr_timesheet` addon) has no
    # per-task `progress` percentage field to average — see
    # docs/implementation/003_module_lines_tasks_milestones_risks.md
    # Technical Decisions. progress_percent is instead the weighted share of
    # progress_weight completed (task.is_closed, standard field computed
    # from task.state), which preserves the "weighted progress" business
    # intent from the execution plan without requiring hr_timesheet.
    progress_percent = fields.Float(
        compute="_compute_progress_percent",
        store=True,
    )
    customer_code = fields.Char(
        related="partner_id.erp_code",
        store=True,
        index=True,
    )
    duration_days = fields.Integer(
        compute="_compute_duration_days",
        inverse="_inverse_duration_days",
        store=True,
    )
    health_status = fields.Selection(
        selection=[
            ("green", "Green"),
            ("amber", "Amber"),
            ("red", "Red"),
        ],
        compute="_compute_health_status",
        store=True,
        index=True,
    )

    @api.depends("module_line_ids")
    def _compute_module_count(self):
        for project in self:
            project.module_count = len(project.module_line_ids)

    @api.depends("module_line_ids.planned_effort", "module_line_ids.actual_effort")
    def _compute_effort_totals(self):
        for project in self:
            project.total_planned_effort = sum(project.module_line_ids.mapped("planned_effort"))
            project.total_actual_effort = sum(project.module_line_ids.mapped("actual_effort"))

    # NOTE: depends/iterates on `tasks`, not the more commonly-used
    # `task_ids`. Core project.project defines `task_ids` with a hardcoded
    # domain=[('is_closed', '=', False)] (see
    # addons/project/models/project_project.py) — it silently excludes
    # closed tasks, which breaks every aggregate here (mandatory_done_count,
    # progress_percent, health_status all need closed tasks to count
    # completion). `tasks` is the same relation without that domain. See
    # docs/implementation/003_module_lines_tasks_milestones_risks.md.
    @api.depends("tasks.is_mandatory", "tasks.is_closed")
    def _compute_mandatory_task_counts(self):
        for project in self:
            mandatory_tasks = project.tasks.filtered("is_mandatory")
            project.mandatory_task_count = len(mandatory_tasks)
            project.mandatory_done_count = len(mandatory_tasks.filtered("is_closed"))

    @api.depends("tasks.progress_weight", "tasks.is_closed")
    def _compute_progress_percent(self):
        for project in self:
            total_weight = sum(project.tasks.mapped("progress_weight"))
            if total_weight:
                done_weight = sum(project.tasks.filtered("is_closed").mapped("progress_weight"))
                project.progress_percent = (done_weight / total_weight) * 100.0
            else:
                project.progress_percent = 0.0

    @api.depends("date_start", "planned_go_live")
    def _compute_duration_days(self):
        for project in self:
            if project.date_start and project.planned_go_live:
                project.duration_days = (project.planned_go_live - project.date_start).days
            else:
                project.duration_days = 0

    def _inverse_duration_days(self):
        for project in self:
            if project.date_start and project.duration_days:
                project.planned_go_live = fields.Date.add(project.date_start, days=project.duration_days)

    @api.depends(
        "progress_percent",
        "date_start",
        "planned_go_live",
        "state",
        "tasks.date_deadline",
        "tasks.is_closed",
        "tasks.is_mandatory",
        "risk_ids.level",
        "risk_ids.state",
    )
    def _compute_health_status(self):
        today = fields.Date.context_today(self)
        for project in self:
            if not project.is_erp_delivery:
                project.health_status = False
                continue

            expected_progress = project._get_expected_progress(today)
            gap = expected_progress - project.progress_percent

            open_tasks = project.tasks.filtered(lambda t: not t.is_closed and t.date_deadline)
            overdue_tasks = open_tasks.filtered(lambda t: t.date_deadline.date() < today)
            overdue_mandatory_tasks = overdue_tasks.filtered("is_mandatory")
            open_critical_risks = project.risk_ids.filtered(lambda r: r.level == "critical" and r.state == "open")
            open_high_risks = project.risk_ids.filtered(lambda r: r.level == "high" and r.state == "open")
            go_live_overdue = bool(
                project.planned_go_live and project.planned_go_live < today and project.state != "done"
            )

            if overdue_mandatory_tasks or open_critical_risks or go_live_overdue or gap > HEALTH_RED_GAP:
                project.health_status = "red"
            elif (
                HEALTH_AMBER_GAP <= gap <= HEALTH_RED_GAP
                or 1 <= len(overdue_tasks) <= HEALTH_AMBER_MAX_OVERDUE_TASKS
                or open_high_risks
            ):
                project.health_status = "amber"
            else:
                project.health_status = "green"

    def _get_expected_progress(self, today):
        """Linear expected-progress percentage based on elapsed time between
        date_start and planned_go_live, clamped to [0, 100]."""
        self.ensure_one()
        if not self.date_start or not self.planned_go_live or self.planned_go_live <= self.date_start:
            return 0.0
        total_days = (self.planned_go_live - self.date_start).days
        elapsed_days = (today - self.date_start).days
        return max(0.0, min(100.0, (elapsed_days / total_days) * 100.0))

    def action_view_erp_module_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Module Lines"),
            "res_model": "erp.project.module.line",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
        }

    def action_view_erp_mandatory_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Mandatory Tasks"),
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id), ("is_mandatory", "=", True)],
            "context": {"default_project_id": self.id},
        }

    @api.model
    def _cron_recompute_health(self):
        active_projects = self.search([
            ("is_erp_delivery", "=", True),
            ("state", "not in", ["done", "cancel"]),
        ])
        active_projects.invalidate_recordset(["health_status"])
        active_projects.modified(["health_status"])

    @api.model
    def get_health_status_dashboard_data(self, domain=None):
        """Sprint 5B performance audit point 2 ("_read_group custom cho
        dashboard"). `health_status` is a stored, indexed field (see
        docs/implementation/003_...md), so Odoo's standard `_read_group`
        already performs the grouping in a single SQL `GROUP BY` query —
        there is no separate non-stored/computed-on-the-fly groupby to hand-
        roll custom SQL for here (that technique is for groupbys that
        aren't plain stored columns, e.g. date-range buckets). This method
        is the dashboard-facing entry point requested by the plan: one
        `_read_group` call, no Python-side looping over records. Verified
        bounded (not O(n)) by
        test_project_performance.py::test_read_group_by_health_status_query_count.
        """
        domain = (domain or []) + [("is_erp_delivery", "=", True)]
        groups = self._read_group(domain, ["health_status"], ["__count"])
        return {health_status or "none": count for health_status, count in groups}

    @api.constrains("is_erp_delivery", "date_start", "planned_go_live")
    def _check_planned_go_live_after_start(self):
        for project in self:
            if (
                project.is_erp_delivery
                and project.date_start
                and project.planned_go_live
                and project.planned_go_live < project.date_start
            ):
                raise ValidationError(self.env._("Planned Go-live date must be on or after the Start date."))

    @api.constrains("state", "actual_go_live")
    def _check_actual_go_live_state(self):
        for project in self:
            if project.actual_go_live and project.state not in ("go_live", "done"):
                raise ValidationError(
                    self.env._("Actual Go-live date can only be set when the project is in the Go-Live or Done state.")
                )

    @api.constrains("contract_value")
    def _check_contract_value_positive(self):
        for project in self:
            if project.contract_value < 0:
                raise ValidationError(self.env._("Contract Value cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_erp_delivery") and not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("erp.project.code")
        return super().create(vals_list)

    def _erp_transition(self, expected_state, target_state, vals=None):
        self.ensure_one()
        if self.state != expected_state:
            raise UserError(
                self.env._(
                    "Cannot move project from state '%(current)s' to '%(target)s': "
                    "it must be in state '%(expected)s' first.",
                    current=self.state,
                    target=target_state,
                    expected=expected_state,
                )
            )
        self.write({"state": target_state, **(vals or {})})

    def action_start_analysis(self):
        for project in self:
            project._erp_transition("draft", "analysis")

    def action_start_implementation(self):
        for project in self:
            project._erp_transition("analysis", "implementation")

    def action_start_uat(self):
        for project in self:
            project._erp_transition("implementation", "uat")

    def action_ready_go_live(self):
        for project in self:
            project._erp_transition("uat", "ready")

    def _check_go_live_conditions(self):
        """Return a list of blocker strings; an empty list means OK to go
        live. This is a hook/extension point: optional addons (e.g. Quality
        Gate in Sprint 5) override this and call super() first, then append
        their own blockers, so the final list is the union of every
        installed addon's checks. Returning a list instead of raising
        directly is what lets the caller (action_go_live) decide when/how to
        raise, and lets subclasses compose their checks on top of this one.
        """
        self.ensure_one()
        blockers = []

        if not self.partner_id:
            blockers.append(self.env._("Customer is required"))
        # NOTE: `user_id` is the ERP Project Manager here, not a separate
        # `pm_id` field — see the NOTE near `member_ids` above (ADR-005).
        if not self.user_id:
            blockers.append(self.env._("Project Manager is required"))
        if not self.module_line_ids:
            blockers.append(self.env._("At least one ERP module is required"))

        # NOTE: `tasks`, not `task_ids` (which has a hardcoded
        # domain=[('is_closed', '=', False)] on project.project and would
        # make `not t.is_closed` always true) — see ADR-012. `is_closed` is
        # the standard project.task field; core `project` has no
        # `stage_id.is_closed` (that field doesn't exist on
        # project.task.type in Odoo 18).
        mandatory_undone = self.tasks.filtered(lambda t: t.is_mandatory and not t.is_closed)
        if mandatory_undone:
            blockers.append(
                self.env._(
                    "Mandatory tasks not completed: %(names)s",
                    names=", ".join(mandatory_undone.mapped("name")),
                )
            )

        critical_open_risks = self.risk_ids.filtered(lambda r: r.level == "critical" and r.state == "open")
        if critical_open_risks:
            blockers.append(self.env._("Open critical risks: %(count)d", count=len(critical_open_risks)))

        if not self.planned_go_live or self.planned_go_live < fields.Date.today():
            blockers.append(self.env._("Planned Go-live date is invalid"))

        return blockers

    def action_go_live(self):
        for project in self:
            blockers = project._check_go_live_conditions()
            if blockers:
                raise UserError(self.env._("Cannot Go-live:\n- %(blockers)s", blockers="\n- ".join(blockers)))
            project._erp_transition("ready", "go_live", {"actual_go_live": fields.Date.today()})

    def action_done(self):
        for project in self:
            project._erp_transition("go_live", "done")

    def action_cancel(self):
        for project in self:
            if project.state in ("done", "cancel"):
                raise UserError(self.env._("A project that is Done or already Cancelled cannot be cancelled."))
            project.write({"state": "cancel"})

    def action_reset_to_draft(self):
        if not self.env.user.has_group("erp_delivery.group_erp_delivery_manager"):
            raise UserError(self.env._("Only an ERP Delivery Manager can reset a project to Draft."))
        for project in self:
            project.write({"state": "draft", "actual_go_live": False})
