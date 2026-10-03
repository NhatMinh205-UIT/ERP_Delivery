from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.fields import Date


@tagged("post_install", "-at_install")
class TestProjectWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Workflow Test Customer",
            "is_erp_customer": True,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Workflow Test Category",
            "code": "WORKFLOW_TEST_CAT",
        })
        cls.solution = cls.env["erp.solution"].create({
            "code": "SOL-WORKFLOW-TEST",
            "name": "Workflow Test Solution",
            "category_id": cls.category.id,
        })

    def _create_project(self, **extra):
        vals = {
            "name": "Workflow Test Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
            "date_start": Date.today(),
            "planned_go_live": Date.today(),
        }
        vals.update(extra)
        return self.env["project.project"].create(vals)

    def test_full_state_sequence(self):
        """draft -> analysis -> implementation -> uat -> ready -> go_live -> done."""
        project = self._create_project()
        self.assertEqual(project.state, "draft")
        self.assertTrue(project.code, "Sequence must auto-assign a code for ERP projects.")

        project.action_start_analysis()
        self.assertEqual(project.state, "analysis")
        project.action_start_implementation()
        self.assertEqual(project.state, "implementation")
        project.action_start_uat()
        self.assertEqual(project.state, "uat")
        project.action_ready_go_live()
        self.assertEqual(project.state, "ready")
        # Sprint 4A: action_go_live() now enforces _check_go_live_conditions()
        # (see test_go_live.py for dedicated coverage); satisfy the "at least
        # one ERP module" condition so this state-machine test is unaffected.
        self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": self.solution.id,
        })
        # Sprint 5: neutralize erp_delivery_quality's extra blocker if that
        # addon happens to be co-installed on this database — see the
        # identical note in tests/test_go_live.py.
        if "quality_threshold" in project._fields:
            project.quality_threshold = 0.0
        project.action_go_live()
        self.assertEqual(project.state, "go_live")
        self.assertEqual(project.actual_go_live, Date.today())
        project.action_done()
        self.assertEqual(project.state, "done")

    def test_invalid_transition_raises_user_error(self):
        """draft -> done directly (skipping intermediate states) must fail."""
        project = self._create_project()
        with self.assertRaises(UserError):
            project.action_go_live()
        self.assertEqual(project.state, "draft")

    def test_planned_go_live_before_start_date_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self._create_project(
                date_start=Date.to_date("2026-06-01"),
                planned_go_live=Date.to_date("2026-01-01"),
            )

    def test_pm_change_is_tracked_in_chatter(self):
        """Changing the Project Manager (user_id) must leave a chatter trail.
        project.project posts a templated assignment notification for
        user_id changes (see addons/project/models/project_project.py)
        rather than a generic tracking_value_ids log, so we assert on
        message count here and verify the generic tracking_value_ids
        mechanism separately below on contract_value."""
        project = self._create_project()
        other_pm = self.env["res.users"].create({
            "name": "Other PM",
            "login": "test_other_pm_login",
            "groups_id": [(6, 0, [self.env.ref("erp_delivery.group_erp_delivery_manager").id])],
        })
        message_domain = [("model", "=", "project.project"), ("res_id", "=", project.id)]
        message_count_before = self.env["mail.message"].search_count(message_domain)
        project.write({"user_id": other_pm.id})
        message_count_after = self.env["mail.message"].search_count(message_domain)
        self.assertGreater(message_count_after, message_count_before)

    def test_contract_value_change_creates_tracking_value(self):
        """contract_value (tracking=True, no special subtype handling) must
        produce a tracking_value_ids entry on write, exercising the generic
        mail.thread tracking mechanism. mail.thread defers tracking-value
        message creation to a cr.precommit hook (see
        addons/mail/models/mail_thread.py _track_prepare/_track_finalize),
        which only runs on an explicit flush/commit — TransactionCase never
        commits, so the hook must be forced with cr.flush()."""
        project = self._create_project(contract_value=1000.0)
        # Flush here first to let create()'s own pending precommit tracking
        # callback for project.project run and clear itself, so it doesn't
        # shadow the one registered below by write() (mail.thread pops its
        # per-model initial_values dict on first run; a second queued
        # callback for the same model would otherwise find it already empty).
        self.env.cr.flush()
        message_domain = [("model", "=", "project.project"), ("res_id", "=", project.id)]
        project.write({"contract_value": 2500.0})
        self.env.cr.flush()
        last_message = self.env["mail.message"].search(message_domain, order="id desc", limit=1)
        tracked_fields = last_message.tracking_value_ids.mapped("field_id.name")
        self.assertIn("contract_value", tracked_fields)
