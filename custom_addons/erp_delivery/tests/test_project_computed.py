from datetime import timedelta

from psycopg2 import IntegrityError

from odoo.fields import Date, Datetime
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestProjectComputed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Computed Test Customer",
            "is_erp_customer": True,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Computed Test Category",
            "code": "COMPUTED_TEST_CAT",
        })
        cls.solution_a = cls.env["erp.solution"].create({
            "code": "SOL-COMPUTED-A",
            "name": "Solution A",
            "category_id": cls.category.id,
        })
        cls.solution_b = cls.env["erp.solution"].create({
            "code": "SOL-COMPUTED-B",
            "name": "Solution B",
            "category_id": cls.category.id,
        })

    def _create_project(self, **extra):
        vals = {
            "name": "Computed Test Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
        }
        vals.update(extra)
        return self.env["project.project"].create(vals)

    def test_progress_percent_weighted_by_mandatory_task(self):
        """unit test 9: add a task with progress_weight=2, is_mandatory=True
        -> progress_percent updates correctly (weighted completion ratio)."""
        project = self._create_project()
        self.env["project.task"].create({
            "name": "Light task",
            "project_id": project.id,
            "progress_weight": 1.0,
            "state": "1_done",
        })
        self.env["project.task"].create({
            "name": "Heavy mandatory task",
            "project_id": project.id,
            "progress_weight": 2.0,
            "is_mandatory": True,
            "state": "01_in_progress",
        })
        # total_weight=3, done_weight=1 (only the light task is closed)
        self.assertAlmostEqual(project.progress_percent, 100 * 1 / 3, places=2)

    def test_actual_effort_aggregation(self):
        """unit test 10: changing a task's actual hours updates the module
        line's actual_effort, which updates the project's
        total_actual_effort (scenario #3 of the exam: aggregate updates when
        source changes)."""
        project = self._create_project()
        module_line = self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": self.solution_a.id,
            "planned_effort": 40.0,
        })
        task = self.env["project.task"].create({
            "name": "Implementation task",
            "project_id": project.id,
            "module_line_id": module_line.id,
            "erp_actual_hours": 5.0,
        })
        self.assertEqual(module_line.actual_effort, 5.0)
        self.assertEqual(project.total_actual_effort, 5.0)

        task.write({"erp_actual_hours": 12.0})
        self.assertEqual(module_line.actual_effort, 12.0)
        self.assertEqual(project.total_actual_effort, 12.0)

    def test_duplicate_module_line_raises_integrity_error(self):
        """unit test 11: inserting a duplicate (project_id, solution_id)
        raises IntegrityError."""
        project = self._create_project()
        self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": self.solution_a.id,
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["erp.project.module.line"].create({
                "project_id": project.id,
                "solution_id": self.solution_a.id,
            })

    def test_duration_days_inverse_sets_planned_go_live(self):
        """unit test 12: setting duration_days=90 sets
        planned_go_live = date_start + 90 days, idempotently (writing back
        duration_days=90 again must still read back as 90, not 89/91)."""
        project = self._create_project(date_start=Date.to_date("2026-01-01"))
        project.duration_days = 90
        self.assertEqual(project.planned_go_live, Date.to_date("2026-01-01") + timedelta(days=90))
        self.assertEqual(project.duration_days, 90)

    def test_health_status_amber_then_red(self):
        """unit test 13: 3 mandatory tasks, complete 1 -> amber; then add an
        overdue mandatory task -> red."""
        today = Date.today()
        project = self._create_project(
            date_start=today - timedelta(days=50),
            planned_go_live=today + timedelta(days=50),
        )
        tasks = self.env["project.task"]
        for i in range(3):
            tasks |= self.env["project.task"].create({
                "name": f"Mandatory task {i}",
                "project_id": project.id,
                "is_mandatory": True,
            })
        tasks[0].write({"state": "1_done"})
        # expected_progress ~= 50%, actual ~= 33.3% -> gap ~16.7 (amber band)
        self.assertEqual(project.health_status, "amber")

        self.env["project.task"].create({
            "name": "Overdue mandatory task",
            "project_id": project.id,
            "is_mandatory": True,
            "date_deadline": Datetime.to_datetime(today - timedelta(days=5)),
        })
        self.assertEqual(project.health_status, "red")
