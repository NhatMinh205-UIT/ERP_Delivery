from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQualityGate(TransactionCase):
    """Scenario #6 of the exam: erp_delivery_quality must work standalone,
    without erp_delivery_sale installed (this test module's addon does not
    depend on it at all — see __manifest__.py)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Quality Gate Test Customer",
            "is_erp_customer": True,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Quality Gate Test Category",
            "code": "QUALITY_TEST_CAT",
        })
        cls.solution = cls.env["erp.solution"].create({
            "code": "SOL-QUALITY-TEST",
            "name": "Quality Gate Test Solution",
            "category_id": cls.category.id,
        })
        cls.criterion_a = cls.env["erp.quality.criterion"].create({
            "name": "Test Criterion A", "code": "TEST_CRIT_A", "category": "task", "weight": 2.0,
        })
        cls.criterion_b = cls.env["erp.quality.criterion"].create({
            "name": "Test Criterion B", "code": "TEST_CRIT_B", "category": "risk", "weight": 1.0,
        })

    def _ready_project(self, **extra):
        vals = {
            "name": "Quality Gate Test Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
            "date_start": Date.today(),
            "planned_go_live": Date.add(Date.today(), days=10),
        }
        vals.update(extra)
        project = self.env["project.project"].create(vals)
        self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": self.solution.id,
        })
        project.action_start_analysis()
        project.action_start_implementation()
        project.action_start_uat()
        project.action_ready_go_live()
        return project

    def test_quality_score_weighted_average(self):
        project = self._ready_project()
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": self.criterion_a.id, "score": 9.0,
        })
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": self.criterion_b.id, "score": 3.0,
        })
        # (9*2 + 3*1) / 3 = 7.0
        self.assertAlmostEqual(project.quality_score, 7.0, places=2)

    def test_go_live_blocked_when_quality_below_threshold(self):
        project = self._ready_project()
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": self.criterion_a.id, "score": 2.0,
        })
        self.assertLess(project.quality_score, project.quality_threshold)
        self.assertFalse(project.is_quality_gate_passed)

        blockers = project._check_go_live_conditions()
        self.assertTrue(any("Quality Score" in b for b in blockers))
        with self.assertRaises(UserError):
            project.action_go_live()
        self.assertEqual(project.state, "ready")

    def test_go_live_succeeds_when_quality_above_threshold(self):
        project = self._ready_project()
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": self.criterion_a.id, "score": 9.0,
        })
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": self.criterion_b.id, "score": 9.0,
        })
        self.assertTrue(project.is_quality_gate_passed)
        self.assertEqual(project._check_go_live_conditions(), [])

        project.action_go_live()
        self.assertEqual(project.state, "go_live")

    def test_base_blockers_still_apply_with_quality_installed(self):
        """Cooperative inheritance must not bypass erp_delivery's own base
        conditions — e.g. a project missing module lines is still blocked
        even if the quality score is fine (no assessments -> quality_score
        defaults to 0.0 < threshold, so this also doubles as a base-blocker
        check with quality active)."""
        project = self.env["project.project"].create({
            "name": "No Module Lines Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
        })
        blockers = project._check_go_live_conditions()
        self.assertTrue(any("ERP module" in b for b in blockers))
