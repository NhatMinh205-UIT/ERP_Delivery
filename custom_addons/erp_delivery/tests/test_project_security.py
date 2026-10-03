from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProjectSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({
            "name": "Security Test Customer",
            "is_erp_customer": True,
        })
        cls.consultant_a = cls.env["res.users"].create({
            "name": "Consultant A",
            "login": "test_consultant_a_login",
            "groups_id": [(6, 0, [cls.env.ref("erp_delivery.group_erp_delivery_consultant").id])],
        })
        cls.consultant_b = cls.env["res.users"].create({
            "name": "Consultant B",
            "login": "test_consultant_b_login",
            "groups_id": [(6, 0, [cls.env.ref("erp_delivery.group_erp_delivery_consultant").id])],
        })
        # Consultants do not have perm_create on project.project (by design,
        # see ir.model.access.csv) so the project is created by an admin/
        # manager context and simply assigned to Consultant A as PM.
        cls.project = cls.env["project.project"].create({
            "name": "Scoped Project",
            "is_erp_delivery": True,
            "partner_id": cls.customer.id,
            "user_id": cls.consultant_a.id,
        })
        cls.category = cls.env["erp.solution.category"].create({
            "name": "Security Test Category",
            "code": "SECURITY_TEST_CAT",
        })
        cls.solution = cls.env["erp.solution"].create({
            "code": "SOL-SECURITY-TEST",
            "name": "Security Test Solution",
            "category_id": cls.category.id,
        })
        cls.module_line = cls.env["erp.project.module.line"].create({
            "project_id": cls.project.id,
            "solution_id": cls.solution.id,
        })
        cls.risk = cls.env["erp.risk"].create({
            "name": "Security Test Risk",
            "project_id": cls.project.id,
        })

    def test_consultant_b_cannot_see_consultant_a_project(self):
        found = self.env["project.project"].with_user(self.consultant_b).search(
            [("id", "=", self.project.id)]
        )
        self.assertFalse(found)

    def test_consultant_a_sees_own_project(self):
        found = self.env["project.project"].with_user(self.consultant_a).search(
            [("id", "=", self.project.id)]
        )
        self.assertEqual(found, self.project)

    def test_consultant_b_sees_project_once_added_as_member(self):
        self.project.write({"member_ids": [(4, self.consultant_b.id)]})
        found = self.env["project.project"].with_user(self.consultant_b).search(
            [("id", "=", self.project.id)]
        )
        self.assertEqual(found, self.project)

    def test_consultant_b_cannot_see_module_line_of_scoped_project(self):
        found = self.env["erp.project.module.line"].with_user(self.consultant_b).search(
            [("id", "=", self.module_line.id)]
        )
        self.assertFalse(found)

    def test_consultant_a_sees_own_project_module_line(self):
        found = self.env["erp.project.module.line"].with_user(self.consultant_a).search(
            [("id", "=", self.module_line.id)]
        )
        self.assertEqual(found, self.module_line)

    def test_consultant_b_cannot_see_risk_of_scoped_project(self):
        found = self.env["erp.risk"].with_user(self.consultant_b).search(
            [("id", "=", self.risk.id)]
        )
        self.assertFalse(found)

    def test_consultant_a_sees_own_project_risk(self):
        found = self.env["erp.risk"].with_user(self.consultant_a).search(
            [("id", "=", self.risk.id)]
        )
        self.assertEqual(found, self.risk)
