from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGoLive(TransactionCase):
    """Sprint 4A — Go-live base workflow: _check_go_live_conditions() and
    action_go_live(). Scenario #4 of the exam ("project cannot go live if
    conditions are not met")."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Go-live Test Customer",
            "is_erp_customer": True,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Go-live Test Category",
            "code": "GOLIVE_TEST_CAT",
        })
        cls.solution = cls.env["erp.solution"].create({
            "code": "SOL-GOLIVE-TEST",
            "name": "Go-live Test Solution",
            "category_id": cls.category.id,
        })

    def _neutralize_optional_addon_blockers(self, project):
        """erp_delivery has zero dependency on erp_delivery_quality (by
        design), but if it happens to ALSO be installed on this database
        (e.g. a combined `-i erp_delivery,erp_delivery_sale,erp_delivery_quality`
        run), its _check_go_live_conditions() override adds a real
        business-logic blocker (quality_score 0.0 < default threshold 7.0)
        that erp_delivery's own tests cannot know about or set up for in
        isolation. This test suite's job is to verify erp_delivery's own 6
        base conditions, not whatever optional addon happens to be
        co-installed, so we neutralize that specific extra condition
        generically (by field presence, no import/dependency on the other
        addon) rather than skip the test outright."""
        if "quality_threshold" in project._fields:
            project.quality_threshold = 0.0

    def _ready_project(self, **extra):
        """A project with every go-live condition satisfied, parked in the
        'ready' state (walked through the full state sequence, not forced
        directly, so the state machine itself is also exercised)."""
        vals = {
            "name": "Go-live Test Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
            "date_start": Date.today(),
            "planned_go_live": Date.add(Date.today(), days=10),
        }
        vals.update(extra)
        project = self.env["project.project"].create(vals)
        self._neutralize_optional_addon_blockers(project)
        self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": self.solution.id,
        })
        project.action_start_analysis()
        project.action_start_implementation()
        project.action_start_uat()
        project.action_ready_go_live()
        return project

    def test_blocked_when_nothing_is_set(self):
        """No partner, no PM, no module lines, no planned_go_live ->
        4 blockers reported, action_go_live raises."""
        project = self.env["project.project"].create({
            "name": "Empty Go-live Test Project",
            "is_erp_delivery": True,
            "user_id": False,
        })
        self._neutralize_optional_addon_blockers(project)
        blockers = project._check_go_live_conditions()
        self.assertEqual(len(blockers), 4)
        joined = "\n".join(blockers)
        self.assertIn("Customer", joined)
        self.assertIn("Project Manager", joined)
        self.assertIn("ERP module", joined)
        self.assertIn("Planned Go-live date", joined)

        with self.assertRaises(UserError):
            project.action_go_live()

    def test_blocked_by_mandatory_task_and_critical_risk(self):
        project = self._ready_project()
        self.env["project.task"].create({
            "name": "Undone mandatory task",
            "project_id": project.id,
            "is_mandatory": True,
        })
        self.env["erp.risk"].create({
            "name": "Unmitigated critical risk",
            "project_id": project.id,
            "level": "critical",
            "state": "open",
        })
        blockers = project._check_go_live_conditions()
        self.assertEqual(len(blockers), 2)
        joined = "\n".join(blockers)
        self.assertIn("Mandatory tasks not completed", joined)
        self.assertIn("Open critical risks", joined)

        with self.assertRaises(UserError):
            project.action_go_live()
        self.assertEqual(project.state, "ready")

    def test_go_live_succeeds_when_all_conditions_met(self):
        project = self._ready_project()
        self.assertEqual(project._check_go_live_conditions(), [])

        project.action_go_live()
        self.assertEqual(project.state, "go_live")
        self.assertEqual(project.actual_go_live, Date.today())

    def test_mandatory_task_blocker_clears_once_task_closed(self):
        project = self._ready_project()
        task = self.env["project.task"].create({
            "name": "Mandatory task to close",
            "project_id": project.id,
            "is_mandatory": True,
        })
        self.assertTrue(project._check_go_live_conditions())

        task.write({"state": "1_done"})
        self.assertEqual(project._check_go_live_conditions(), [])
        project.action_go_live()
        self.assertEqual(project.state, "go_live")
