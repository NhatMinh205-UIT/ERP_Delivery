from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestCustomerAndSolution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Sales Suite",
            "code": "TEST_SALES",
        })
        cls.solution = cls.env["erp.solution"].create({
            "code": "SOL-TEST-01",
            "name": "Test Solution",
            "category_id": cls.category.id,
            "service_price": 1000.0,
            "internal_cost": 400.0,
        })
        cls.company_b = cls.env["res.company"].create({"name": "Company B"})

    def test_erp_code_duplicate_raises_integrity_error(self):
        """Creating two ERP customers with the same erp_code in the same
        company must fail. company_id is set explicitly: res.partner leaves
        company_id empty (NULL) by default, and Postgres treats NULL values
        as distinct for UNIQUE purposes, so the constraint would not trigger
        without pinning both records to the same company."""
        self.env["res.partner"].create({
            "name": "Customer One",
            "is_erp_customer": True,
            "erp_code": "CUST-001",
            "company_id": self.env.company.id,
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["res.partner"].create({
                "name": "Customer Two",
                "is_erp_customer": True,
                "erp_code": "CUST-001",
                "company_id": self.env.company.id,
            })

    def test_consultant_cannot_read_internal_cost(self):
        """A plain user (without Manager group) must not see internal_cost.
        Odoo 18 enforces field-level groups by raising AccessError when an
        explicitly-requested field is not allowed for the user, rather than
        silently dropping it from the result."""
        user = self.env["res.users"].create({
            "name": "Test Consultant",
            "login": "test_consultant_login",
            "groups_id": [(6, 0, [
                self.env.ref("erp_delivery.group_erp_delivery_consultant").id,
                self.env.ref("base.group_user").id,
            ])],
        })
        with self.assertRaises(AccessError):
            self.solution.with_user(user).read(["name", "internal_cost"])

        # Reading without explicitly requesting internal_cost works fine and
        # the field is simply absent from the result.
        result = self.solution.with_user(user).read(["name"])
        self.assertNotIn("internal_cost", result[0])

    def test_internal_cost_is_company_dependent(self):
        """internal_cost must differ per company since it is company_dependent."""
        self.solution.with_company(self.env.company).internal_cost = 400.0
        self.solution.with_company(self.company_b).internal_cost = 999.0

        self.assertEqual(self.solution.with_company(self.env.company).internal_cost, 400.0)
        self.assertEqual(self.solution.with_company(self.company_b).internal_cost, 999.0)
