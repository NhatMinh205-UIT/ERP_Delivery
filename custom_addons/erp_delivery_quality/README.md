# erp_delivery_quality

## Purpose

Optional. Quality scoring and Go-live gate. Installable and fully
functional **without** `erp_delivery_sale` (scenario #6 of the exam) —
depends only on `erp_delivery`.

- `erp.quality.criterion` (master data), `erp.quality.assessment`
  (per-project scoring record)
- `project.project.quality_score` (weighted avg, compute+store),
  `quality_threshold` (company_dependent, default 7.0),
  `is_quality_gate_passed` (compute)
- **Cooperative inheritance**: overrides `_check_go_live_conditions()`,
  calls `super()` first (erp_delivery's 6 base conditions always run),
  appends a quality blocker if `quality_score < quality_threshold`
- **Bridge case**: if `erp_delivery_sale` also happens to be installed
  (checked via `'erp_sale_order_id' in self._fields` — field-existence, not
  `'sale.order' in self.env`; see
  `docs/implementation/005_quality_gate_performance_docs.md`), also checks
  `contract_value` vs the source SO's `amount_total` (>5% discrepancy
  blocks go-live)

## Dependency graph

```
erp_delivery  →  erp_delivery_quality
```

Deliberately **not** depending on `erp_delivery_sale` or `sale_management`
— see Technical Decisions in
`docs/implementation/005_quality_gate_performance_docs.md`.

## Folder structure

```
erp_delivery_quality/
├── models/    erp_quality_criterion, erp_quality_assessment, project_project
├── views/     project_project (Quality tab), erp_quality (criteria config)
├── security/  record rules, ir.model.access.csv
├── data/      4 seed quality criteria
└── tests/     4 standalone tests + 1 cooperative-inheritance test
             (skipped unless erp_delivery_sale is ALSO installed)
```

## Setup

```bash
odoo-bin --addons-path=... -d <db> -i erp_delivery_quality
```

Run tests: `-i erp_delivery_quality --test-enable --test-tags /erp_delivery_quality --stop-after-init`.
To exercise the cooperative-inheritance test, install all 3 addons together:
`-i erp_delivery,erp_delivery_sale,erp_delivery_quality --test-enable --test-tags /erp_delivery_quality`.
