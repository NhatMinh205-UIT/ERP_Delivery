# erp_delivery (Core)

## Purpose

Core ERP implementation delivery management. Mandatory addon — the other
two (`erp_delivery_sale`, `erp_delivery_quality`) both depend on it, but it
depends on neither.

- ERP Customer (`res.partner` extension)
- Solution catalog (`erp.solution`, `erp.solution.category`)
- ERP Delivery Project (`project.project` extension): 8-state workflow,
  sequence-generated `code`, 10 computed fields (incl. `health_status`
  store+index), daily cron recompute
- Module Lines (`erp.project.module.line`), Task extension (`project.task`),
  Milestone extension (`project.milestone`), Risk (`erp.risk`)
- `_check_go_live_conditions()` — the cooperative-inheritance hook that
  `erp_delivery_quality` extends
- Security: 3 groups (User ⊂ Consultant ⊂ Manager), ACL, record rules,
  field-level groups

## Dependency graph

```
base, mail, project, contacts  →  erp_delivery
```

No dependency on `sale_management`/`sale_project` or `hr_timesheet` — see
`docs/implementation/003_module_lines_tasks_milestones_risks.md` and
`004_go_live_base_and_sales_integration.md` at the repo root for why those
were deliberately avoided.

## Folder structure

```
erp_delivery/
├── models/      res_partner, erp_solution(_category), project_project,
│                project_task, project_milestone, erp_risk,
│                erp_project_module_line
├── views/       res_partner, erp_solution, project_project, menus
├── security/    groups + record rules, ir.model.access.csv
├── data/        sequence, solution categories (seed), cron
└── tests/       22+ TransactionCase tests (workflow, security,
                 multi-company, computed fields, go-live, performance)
```

## Setup

```bash
odoo-bin --addons-path=<odoo_addons>,<odoo_core_addons>,<this_repo>/custom_addons \
  -d <db> -i erp_delivery
```

Run tests: `-i erp_delivery --test-enable --test-tags /erp_delivery --stop-after-init`.
