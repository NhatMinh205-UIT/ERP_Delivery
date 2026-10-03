# erp_delivery_sale

## Purpose

Optional. Creates an ERP Delivery Project directly from a confirmed Sale
Order, with 2-way smart-button navigation. Installable and fully
functional **without** `erp_delivery_quality` (scenario #5 of the exam).

- `sale.order.erp_project_id` / `is_erp_ready` (compute)
- `sale.order.action_create_erp_project()` — syncs `partner_id` and
  `contract_value` from the SO, posts a chatter message referencing the
  source SO
- `project.project.erp_sale_order_id` — **not** `sale_order_id` (see
  `docs/implementation/004_go_live_base_and_sales_integration.md`,
  Technical Decisions: the standard `sale_project` addon already defines a
  different `sale_order_id` field on `project.project`)
- `UNIQUE(erp_sale_order_id)` SQL constraint — race-condition-safe, one SO
  can only generate one project

## Dependency graph

```
erp_delivery, sale_management  →  erp_delivery_sale
```

## Folder structure

```
erp_delivery_sale/
├── models/   sale_order, project_project
├── views/    sale_order_views, project_project_views
└── tests/    5 TransactionCase tests
```

## Setup

```bash
odoo-bin --addons-path=... -d <db> -i erp_delivery_sale
```

Requires `erp_delivery` and `sale_management` already present on the
addons path (installed automatically as dependencies). Run tests:
`-i erp_delivery_sale --test-enable --test-tags /erp_delivery_sale --stop-after-init`.
