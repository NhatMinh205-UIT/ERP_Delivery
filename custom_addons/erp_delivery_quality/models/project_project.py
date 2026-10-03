from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    quality_score = fields.Float(
        compute="_compute_quality_score",
        store=True,
    )
    quality_threshold = fields.Float(
        default=7.0,
        company_dependent=True,
    )
    quality_assessment_ids = fields.One2many(
        comodel_name="erp.quality.assessment",
        inverse_name="project_id",
    )
    is_quality_gate_passed = fields.Boolean(
        compute="_compute_is_quality_gate_passed",
    )

    @api.depends("quality_assessment_ids.score", "quality_assessment_ids.criterion_id.weight")
    def _compute_quality_score(self):
        for project in self:
            assessments = project.quality_assessment_ids
            if not assessments:
                project.quality_score = 0.0
                continue
            total_weight = sum(assessments.mapped("criterion_id.weight"))
            if total_weight:
                project.quality_score = sum(
                    a.score * a.criterion_id.weight for a in assessments
                ) / total_weight
            else:
                project.quality_score = 0.0

    @api.depends("quality_score", "quality_threshold")
    def _compute_is_quality_gate_passed(self):
        for project in self:
            project.is_quality_gate_passed = project.quality_score >= project.quality_threshold

    def _check_go_live_conditions(self):
        # CRITICAL: call super() first — cooperative inheritance. This lets
        # erp_delivery's own 6 base conditions run regardless of install
        # order, and this addon only ever appends to that list, never
        # replaces it.
        blockers = super()._check_go_live_conditions()

        if self.quality_score < self.quality_threshold:
            blockers.append(
                self.env._(
                    "Quality Score (%(score).2f) below threshold (%(threshold).2f)",
                    score=self.quality_score,
                    threshold=self.quality_threshold,
                )
            )

        # Bridge case: erp_delivery_quality does NOT depend on
        # erp_delivery_sale (manifest), so `erp_sale_order_id` may not exist
        # on this model at all. The execution plan's own sketch checks
        # `'sale.order' in self.env`, but that only proves the `sale`/
        # `sale_management` app is installed — NOT that erp_delivery_sale
        # (the addon that actually defines `erp_sale_order_id`) is. Checking
        # the field's presence in `self._fields` is the precise condition
        # for "is erp_delivery_sale installed", and avoids an AttributeError
        # when Sales integration isn't installed. See
        # docs/implementation/005_quality_gate_performance_docs.md,
        # Technical Decisions.
        if "erp_sale_order_id" in self._fields and self.erp_sale_order_id:
            if self.contract_value < self.erp_sale_order_id.amount_total * 0.95:
                blockers.append(self.env._("Contract value discrepancy vs source SO (>5%)"))

        return blockers
