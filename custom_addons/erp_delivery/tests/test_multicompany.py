from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMultiCompanyIsolation(TransactionCase):
    """Scenario #2 of the exam: no data leak between companies. Mirrors the
    execution plan's own example (mục 4.4), adapted to this addon's actual
    group names (erp_delivery.group_erp_delivery_manager) and the
    is_erp_delivery-scoped record rules (ADR-008)."""

    def test_no_data_leak_between_companies(self):
        company_a = self.env["res.company"].create({"name": "Company A (multicompany test)"})
        company_b = self.env["res.company"].create({"name": "Company B (multicompany test)"})

        project_a = self.env["project.project"].with_company(company_a).create({
            "name": "Project A",
            "is_erp_delivery": True,
            "company_id": company_a.id,
        })

        user_b = self.env["res.users"].create({
            "name": "Manager B (multicompany test)",
            "login": "test_manager_b_multicompany_login",
            "company_id": company_b.id,
            "company_ids": [(6, 0, [company_b.id])],
            "groups_id": [(4, self.env.ref("erp_delivery.group_erp_delivery_manager").id)],
        })

        accessible = self.env["project.project"].with_user(user_b).search(
            [("id", "=", project_a.id)]
        )
        self.assertFalse(accessible, "Manager B must not see Company A's project via search.")

        with self.assertRaises(AccessError):
            project_a.with_user(user_b).read(["name"])

    def test_internal_cost_differs_between_companies(self):
        """Complements the multi-company scenario: internal_cost
        (company_dependent=True, Sprint 1 ADR-002) must store a different
        value per company context for the same shared solution record."""
        company_a = self.env["res.company"].create({"name": "Company A (cost test)"})
        company_b = self.env["res.company"].create({"name": "Company B (cost test)"})
        category = self.env["erp.solution.category"].create({
            "name": "Multicompany Test Category",
            "code": "MULTICOMPANY_TEST_CAT",
        })
        solution = self.env["erp.solution"].create({
            "code": "SOL-MULTICOMPANY-TEST",
            "name": "Multicompany Test Solution",
            "category_id": category.id,
        })

        solution.with_company(company_a).internal_cost = 100.0
        solution.with_company(company_b).internal_cost = 999.0

        self.assertEqual(solution.with_company(company_a).internal_cost, 100.0)
        self.assertEqual(solution.with_company(company_b).internal_cost, 999.0)
