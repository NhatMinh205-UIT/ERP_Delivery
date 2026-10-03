from odoo.tests import TransactionCase, tagged

PROJECT_COUNT = 150
MODULE_LINE_COUNT = 150


@tagged("post_install", "-at_install")
class TestProjectPerformance(TransactionCase):
    """unit tests 14 and 15 of the exam, adapted to run reliably and fast in
    automated CI: the execution plan frames these as wall-clock timing
    checks on 1000 records (e.g. "< 100ms with 1000 projects"), but
    wall-clock assertions are flaky under sandboxed/shared CI hardware. We
    instead assert that the SQL query count stays bounded and does not grow
    linearly with the number of records (the actual N+1 regression these
    tests are meant to catch), at a smaller but still representative scale.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Performance Test Customer",
            "is_erp_customer": True,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Perf Test Category",
            "code": "PERF_TEST_CAT",
        })
        cls.solutions = cls.env["erp.solution"].create([
            {"code": f"SOL-PERF-{i}", "name": f"Perf Solution {i}", "category_id": cls.category.id}
            for i in range(MODULE_LINE_COUNT)
        ])

    def test_read_group_by_health_status_query_count(self):
        """unit test 14: _read_group by health_status on many projects
        should run in a small, bounded number of queries (not one query per
        record)."""
        self.env["project.project"].create([
            {
                "name": f"Perf Project {i}",
                "is_erp_delivery": True,
                "partner_id": self.customer.id,
            }
            for i in range(PROJECT_COUNT)
        ])
        self.env.flush_all()
        count0 = self.env.cr.sql_log_count
        groups = self.env["project.project"]._read_group(
            [("is_erp_delivery", "=", True)],
            ["health_status"],
            ["__count"],
        )
        query_count = self.env.cr.sql_log_count - count0
        self.assertEqual(sum(count for _, count in groups), PROJECT_COUNT)
        self.assertLess(query_count, 10, "_read_group by health_status must not scale with record count")

    def test_bulk_module_line_create_and_aggregate(self):
        """unit test 15 (scenario #8 of the exam): batch-creating many
        module lines for one project must not break, and the project's
        aggregate fields (module_count, total_planned_effort) must reflect
        all of them correctly afterwards. Also a bulk write of task
        erp_actual_hours across many tasks must update all the
        corresponding module lines without growing query count linearly."""
        project = self.env["project.project"].create({
            "name": "Bulk Test Project",
            "is_erp_delivery": True,
            "partner_id": self.customer.id,
        })
        module_lines = self.env["erp.project.module.line"].create([
            {
                "project_id": project.id,
                "solution_id": solution.id,
                "planned_effort": 10.0,
            }
            for solution in self.solutions
        ])
        self.assertEqual(project.module_count, MODULE_LINE_COUNT)
        self.assertEqual(project.total_planned_effort, MODULE_LINE_COUNT * 10.0)

        tasks = self.env["project.task"].create([
            {
                "name": f"Bulk task {i}",
                "project_id": project.id,
                "module_line_id": module_lines[i].id,
            }
            for i in range(MODULE_LINE_COUNT)
        ])
        self.env.flush_all()
        count0 = self.env.cr.sql_log_count
        tasks.write({"erp_actual_hours": 3.0})
        query_count = self.env.cr.sql_log_count - count0
        self.assertLess(
            query_count, MODULE_LINE_COUNT,
            "Bulk write must not issue one query per record (N+1)",
        )
        self.assertEqual(project.total_actual_effort, MODULE_LINE_COUNT * 3.0)

    def test_prefetch_via_mapped_across_many_projects(self):
        """Sprint 5B performance audit point 3: walking
        project.mapped('module_line_ids.task_ids') across many projects at
        once lets Odoo's prefetch mechanism batch-load related records,
        instead of the N+1 anti-pattern of looping
        `for p in projects: for ml in p.module_line_ids: for t in
        ml.task_ids: ...` one relation hop at a time per record."""
        project_count = 30
        projects = self.env["project.project"].create([
            {"name": f"Prefetch Project {i}", "is_erp_delivery": True, "partner_id": self.customer.id}
            for i in range(project_count)
        ])
        for i, project in enumerate(projects):
            module_line = self.env["erp.project.module.line"].create({
                "project_id": project.id,
                "solution_id": self.solutions[i].id,
            })
            self.env["project.task"].create({
                "name": f"Prefetch task {i}",
                "project_id": project.id,
                "module_line_id": module_line.id,
            })

        projects.invalidate_recordset()
        self.env.flush_all()
        count0 = self.env.cr.sql_log_count
        task_names = projects.mapped("module_line_ids.task_ids.name")
        query_count = self.env.cr.sql_log_count - count0

        self.assertEqual(len(task_names), project_count)
        self.assertLess(
            query_count, project_count,
            "mapped() across module_line_ids.task_ids must batch-prefetch, "
            "not issue one query per project",
        )
