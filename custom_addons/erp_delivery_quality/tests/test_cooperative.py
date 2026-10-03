import unittest

from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCooperativeValidation(TransactionCase):
    """Scenario #7 of the exam: when both optional addons (erp_delivery_sale
    and erp_delivery_quality) are installed together, both validations run
    and compose (cooperative inheritance via super()). This test is skipped
    unless both are actually installed on the database it runs against —
    it cannot run from erp_delivery_quality's own `-i` alone."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        both_installed = cls.env["ir.module.module"].search_count([
            ("name", "in", ["erp_delivery_sale", "erp_delivery_quality"]),
            ("state", "=", "installed"),
        ])
        if both_installed != 2:
            raise unittest.SkipTest("Both erp_delivery_sale and erp_delivery_quality must be installed for this test.")

    def test_both_validations_run_and_compose(self):
        customer = self.env["res.partner"].create({
            "name": "Cooperative Test Customer",
            "is_erp_customer": True,
        })
        category = self.env["erp.solution.category"].create({
            "name": "Cooperative Test Category",
            "code": "COOP_TEST_CAT",
        })
        solution = self.env["erp.solution"].create({
            "code": "SOL-COOP-TEST",
            "name": "Cooperative Test Solution",
            "category_id": category.id,
        })
        product = self.env["product.product"].create({
            "name": "Cooperative Test Service",
            "type": "service",
            "list_price": 10000.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": customer.id,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1})],
        })
        order.action_confirm()
        order.action_create_erp_project()
        project = order.erp_project_id

        self.env["erp.project.module.line"].create({
            "project_id": project.id,
            "solution_id": solution.id,
        })
        project.write({
            "date_start": Date.today(),
            "planned_go_live": Date.add(Date.today(), days=10),
        })
        project.action_start_analysis()
        project.action_start_implementation()
        project.action_start_uat()
        project.action_ready_go_live()

        # Fail BOTH checks at once: low quality score, and a contract_value
        # that diverges from the source SO's amount_total by more than 5%.
        criterion = self.env["erp.quality.criterion"].create({
            "name": "Coop Criterion", "code": "COOP_CRIT", "category": "task", "weight": 1.0,
        })
        self.env["erp.quality.assessment"].create({
            "project_id": project.id, "criterion_id": criterion.id, "score": 2.0,
        })
        project.contract_value = order.amount_total * 0.5

        with self.assertRaises(UserError) as capture:
            project.action_go_live()

        message = str(capture.exception)
        self.assertIn("Quality Score", message)
        self.assertIn("Contract value discrepancy", message)
