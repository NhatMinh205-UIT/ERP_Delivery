from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestSalesIntegration(TransactionCase):
    """Sprint 4B. Scenario #5 of the exam: erp_delivery_sale installed
    without erp_delivery_quality must work standalone (this module does not
    depend on erp_delivery_quality at all — see __manifest__.py)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Sales Integration Test Customer",
            "is_erp_customer": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "ERP Implementation Service",
            "type": "service",
            "list_price": 5000.0,
        })

    def _create_confirmed_order(self, qty=2):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": qty,
            })],
        })
        order.action_confirm()
        return order

    def test_full_workflow_so_to_erp_project(self):
        """unit test 16: SO -> ERP project full round trip works with only
        erp_delivery_sale installed."""
        order = self._create_confirmed_order()
        self.assertTrue(order.is_erp_ready)

        result = order.action_create_erp_project()
        self.assertEqual(result["res_model"], "project.project")
        project = self.env["project.project"].browse(result["res_id"])

        self.assertEqual(order.erp_project_id, project)
        self.assertTrue(project.is_erp_delivery)
        self.assertFalse(order.is_erp_ready, "is_erp_ready must turn off once a project exists")

    def test_second_project_from_same_order_raises_integrity_error(self):
        """unit test 17: creating a second ERP project from the same SO must
        fail at the SQL level (UNIQUE constraint), not just a Python guard
        (race-condition safe, per the execution plan's own rationale)."""
        order = self._create_confirmed_order()
        order.action_create_erp_project()

        # The Python guard catches the obvious case (same order, same
        # erp_project_id already set):
        with self.assertRaises(UserError):
            order.action_create_erp_project()

        # The SQL constraint is the real guard against a race between two
        # concurrent requests that both pass the Python guard before either
        # writes erp_project_id: simulate that by creating a second project
        # pointing at the same order directly, bypassing action_create_erp_project.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["project.project"].create({
                "name": "Duplicate ERP Project",
                "is_erp_delivery": True,
                "partner_id": self.customer.id,
                "erp_sale_order_id": order.id,
            })

    def test_partner_and_contract_value_synced_on_creation(self):
        """unit test 18: confirming a SO then creating the ERP project syncs
        partner_id and contract_value from the SO."""
        order = self._create_confirmed_order(qty=3)
        order.action_create_erp_project()
        project = order.erp_project_id

        self.assertEqual(project.partner_id, order.partner_id)
        self.assertEqual(project.contract_value, order.amount_total)

    def test_smart_buttons_navigate_both_ways(self):
        """unit test 19: smart button actions on both sides point at the
        right record."""
        order = self._create_confirmed_order()
        order.action_create_erp_project()
        project = order.erp_project_id

        so_to_project = order.action_view_erp_project()
        self.assertEqual(so_to_project["res_model"], "project.project")
        self.assertEqual(so_to_project["res_id"], project.id)

        project_to_so = project.action_view_erp_source_sale_order()
        self.assertEqual(project_to_so["res_model"], "sale.order")
        self.assertEqual(project_to_so["res_id"], order.id)

    def test_project_chatter_references_source_order(self):
        """DoD Milestone 4: new project's chatter must reference the
        source SO."""
        order = self._create_confirmed_order()
        order.action_create_erp_project()
        project = order.erp_project_id

        messages = project.message_ids.mapped("body")
        self.assertTrue(any(order.name in (body or "") for body in messages))
