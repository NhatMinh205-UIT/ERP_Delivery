from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    erp_project_id = fields.Many2one(
        comodel_name="project.project",
        string="ERP Delivery Project",
        readonly=True,
        copy=False,
    )
    is_erp_ready = fields.Boolean(compute="_compute_is_erp_ready")

    @api.depends("state", "erp_project_id")
    def _compute_is_erp_ready(self):
        for order in self:
            order.is_erp_ready = order.state == "sale" and not order.erp_project_id

    def action_create_erp_project(self):
        self.ensure_one()
        if self.erp_project_id:
            raise UserError(self.env._("This Sale Order already has an ERP project."))

        project = self.env["project.project"].create({
            "name": self.env._("ERP Delivery - %s", self.name),
            "is_erp_delivery": True,
            "partner_id": self.partner_id.id,
            "contract_value": self.amount_total,
            "erp_sale_order_id": self.id,
            "company_id": self.company_id.id,
        })
        project.message_post(
            body=self.env._("Project created from Sale Order %s.", self.name)
        )
        self.erp_project_id = project.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.project",
            "res_id": project.id,
            "view_mode": "form",
        }

    def action_view_erp_project(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.project",
            "res_id": self.erp_project_id.id,
            "view_mode": "form",
        }
