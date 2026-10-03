# Quality Gate, Performance Audit & Documentation (Sprint 5 — Tuần 9–10)

## 1. Mục tiêu

Addon `erp_delivery_quality` hoàn chỉnh (cooperative inheritance với
`_check_go_live_conditions()`), audit performance 5 điểm, đủ 8 test
scenario của đề, `README.md` cho mỗi addon + `TECHNICAL_NOTES.md` ở repo
root — hoàn thiện toàn bộ dự án.

## 2. Requirement liên quan

`ERP_Delivery_Execution_Plan.md`, mục 3 — **Sprint 5 (Tuần 9–10): Quality
Gate + Performance + Tests + Docs**.

## 3. Trạng thái trước khi thay đổi — Audit Sprint 1–4

Đọc lại toàn bộ code hiện có trước khi code (theo yêu cầu, đặc biệt kiểm
tra hook `_check_go_live_conditions()`):

- `erp_delivery/models/project_project.py`: `_check_go_live_conditions()`
  (Sprint 4A) đã **đúng chuẩn hook/extension point** — trả về `list`
  blocker (không raise trực tiếp), `action_go_live()` gọi method này rồi
  mới raise `UserError` ở caller. Đây chính xác là điểm neo mà
  `erp_delivery_quality` cần `super()` vào — **xác nhận không cần sửa gì ở
  `erp_delivery` cho việc này**, chỉ cần override đúng cách ở addon mới.
- `erp_delivery/models/project_project.py` dùng `self.tasks` (không phải
  `task_ids`) và `t.is_closed` (ADR-012) — đã đúng, addon quality không
  cần lo lại vấn đề này.
- `erp_delivery_sale`: field `erp_project_id`/`erp_sale_order_id` (ADR-013,
  **không** phải `sale_order_id` thuần như plan) — quan trọng cho bridge
  case check ở `erp_delivery_quality`.
- 31 test (Sprint 1–4) đều PASS trước khi bắt đầu Sprint 5.

### Phát hiện quan trọng #1 — audit trước khi code

`erp.quality.criterion`/`erp.quality.assessment`: không có model chuẩn
tương đương trong Odoo 18 core (khác với trường hợp `erp.milestone` ở
Sprint 3) — tạo mới đúng như plan, không có xung đột.

## 4. Thiết kế

### Models (`erp_delivery_quality`, mới hoàn toàn)

| Model | Kỹ thuật | Field chính |
|---|---|---|
| `erp.quality.criterion` | Mới | `name`, `code` (unique), `weight`, `category` (task/milestone/risk/commercial), `active` |
| `erp.quality.assessment` | Mới, `_inherit=['mail.thread']` | `project_id`, `criterion_id`, `score` (0–10, constraint), `note`, `assessed_by`, `assessed_date`. **Thêm so với plan**: `UNIQUE(project_id, criterion_id)` — tránh đánh giá trùng 1 tiêu chí 2 lần cho cùng project (judgment call, nhất quán với pattern `erp.project.module.line` ở Sprint 3) |
| `project.project` | `_inherit` | `quality_score` (compute+store, weighted avg), `quality_threshold` (`company_dependent=True`, default 7.0 — **Float, không phải Monetary**, nên không gặp lại vấn đề ADR-002), `quality_assessment_ids` (O2m), `is_quality_gate_passed` (compute) |

### Cooperative inheritance

```python
def _check_go_live_conditions(self):
    blockers = super()._check_go_live_conditions()   # erp_delivery's 6 base conditions, always run first
    if self.quality_score < self.quality_threshold:
        blockers.append(...)
    if "erp_sale_order_id" in self._fields and self.erp_sale_order_id:
        if self.contract_value < self.erp_sale_order_id.amount_total * 0.95:
            blockers.append(...)
    return blockers
```

Xem `TECHNICAL_NOTES.md` mục 2–3 cho giải trình đầy đủ pattern này và bridge
case — không lặp lại ở đây.

## 5. Files thay đổi

**`erp_delivery`** (Sprint 5B — performance audit)

| File | Thay đổi |
|---|---|
| `models/project_project.py` | Thêm `index=True` cho `state`, `planned_go_live`, `partner_id`, `user_id`; thêm `get_health_status_dashboard_data()` |
| `models/res_partner.py` | Đổi label `company_currency_id` từ "Currency" → "ERP Subscription Currency" (tránh trùng label với field `currency_id` của module `account` — phát hiện thực tế khi test tổ hợp cài đặt, xem mục 11) |
| `tests/test_multicompany.py` | Mới (scenario #2 của đề) |
| `tests/test_project_performance.py` | Thêm `test_prefetch_via_mapped_across_many_projects` (Sprint 5B điểm 3) |
| `tests/test_go_live.py`, `tests/test_project_workflow.py` | Thêm `_neutralize_optional_addon_blockers()` — xem Technical Decisions |
| `tests/__init__.py` | Thêm import |
| `README.md` | Mới |

**`erp_delivery_quality`** (toàn bộ mới)

| File | |
|---|---|
| `__manifest__.py`, `__init__.py`, `README.md` | |
| `models/__init__.py`, `erp_quality_criterion.py`, `erp_quality_assessment.py`, `project_project.py` | |
| `security/erp_delivery_quality_security.xml`, `security/ir.model.access.csv` | |
| `data/quality_criterion_data.xml` | 4 tiêu chí seed |
| `views/project_project_views.xml`, `views/erp_quality_views.xml` | |
| `tests/__init__.py`, `test_quality_gate.py` (4 test), `test_cooperative.py` (1 test, `skipUnless` cả 2 addon cùng cài) | |

**Repo root**

| File | |
|---|---|
| `TECHNICAL_NOTES.md` | Mới — 12 câu hỏi giải trình, cooperative inheritance, bridge case, 5 điểm performance |
| `README.md` | Cập nhật trạng thái Sprint 5 |

## 6. Giải thích implementation

```
Manager mở tab "Quality" trên project form (erp_delivery_quality cài)
    ↓
Thêm assessment cho từng criterion (score 0-10)
    ↓
quality_score = weighted avg (compute+store) tự cập nhật
    ↓
is_quality_gate_passed = (quality_score >= quality_threshold) tự cập nhật
    ↓
PM bấm "Go-Live" → action_go_live() → _check_go_live_conditions()
    ↓
MRO: erp_delivery_quality._check_go_live_conditions() chạy TRƯỚC (vì nó
override), gọi super() → erp_delivery's 6 base condition chạy, trả blockers
    ↓
erp_delivery_quality append thêm blocker Quality (+ Commercial nếu
erp_sale_order_id tồn tại và lệch >5%)
    ↓
action_go_live() raise UserError DUY NHẤT với TOÀN BỘ blocker từ cả 2 addon
```

## 7. Security

- Không có group mới — tái dùng `erp_delivery.group_erp_delivery_{consultant,manager}`.
- Record rules cho `erp.quality.assessment` theo đúng pattern Sprint 3 (scope
  qua `project_id.is_erp_delivery`/`user_id`/`member_ids`/`company_id`).
- `erp.quality.criterion`: master data, User/Consultant chỉ đọc, Manager
  full CRUD (giống `erp.solution` Sprint 1).
- `quality_threshold`: `company_dependent=True` — đã có sẵn cơ chế bảo vệ
  qua field này là Float (không groups= riêng, nhưng hiển thị trong view
  chỉ cho Manager thấy/sửa qua `groups="erp_delivery.group_erp_delivery_manager"`
  ở view level).

## 8. Performance (Sprint 5B — đủ 5 điểm, có test đo thật)

| # | Điểm | Trạng thái | Test |
|---|---|---|---|
| 1 | N+1 list view | Đã đạt từ Sprint 2–3 (toàn bộ field list đều `store=True`) | — |
| 2 | `_read_group` dashboard | `get_health_status_dashboard_data()` — 1 lệnh `_read_group` | `test_read_group_by_health_status_query_count` (Sprint 3, vẫn PASS) |
| 3 | Prefetch module_line+task | `projects.mapped('module_line_ids.task_ids...')` | `test_prefetch_via_mapped_across_many_projects` (mới) |
| 4 | Index bổ sung | Thêm `state`, `planned_go_live`, `partner_id`, `user_id` (`index=True`) | Verify qua install không lỗi + `\d project_project` (xem mục 10) |
| 5 | Bulk import / norecompute | **`env.norecompute()` không tồn tại trong Odoo 18** — ORM tự batch recompute qua `@api.model_create_multi` | `test_bulk_module_line_create_and_aggregate` (Sprint 3, vẫn PASS) |

Chi tiết đầy đủ trade-off từng điểm: `TECHNICAL_NOTES.md` mục 4.

## 9. Tests — đủ 8 scenario của đề

| # | Scenario | Coverage | Trạng thái |
|---|---|---|---|
| 1 | Consultant không access project ngoài scope | `test_project_security.py` (Sprint 2) | PASS (chạy lại) |
| 2 | Multi-company không rò data | `test_multicompany.py` (**mới, Sprint 5**) | PASS |
| 3 | Aggregate cập nhật khi source đổi | `test_project_computed.py` (Sprint 3) | PASS (chạy lại) |
| 4 | Project không Go-live nếu điều kiện chưa đạt | `test_go_live.py` (Sprint 4A) | PASS (chạy lại) |
| 5 | Sales hoạt động không có Quality | `test_sales_integration.py` (Sprint 4B, addon không depend quality) | PASS |
| 6 | Quality hoạt động không có Sales | `test_quality_gate.py` (**mới, Sprint 5**, addon không depend sale) | PASS |
| 7 | Cả 2 cùng cài, validation cả 2 đều chạy | `test_cooperative.py` (**mới, Sprint 5**, `unittest.SkipTest` nếu thiếu 1 trong 2) | PASS (khi cài cả 3) |
| 8 | Batch create không phá logic | `test_project_performance.py` (Sprint 3) | PASS (chạy lại) |

**Toàn bộ 8/8 scenario chạy thật và PASS** — không có scenario nào chỉ suy
luận lý thuyết.

## 10. Validation Result

### Executed

```bash
# erp_delivery_quality alone
createdb erp_delivery_test
odoo-bin -d erp_delivery_test -i erp_delivery_quality --test-enable --test-tags /erp_delivery_quality --stop-after-init

# Cả 3 addon cùng cài + full test suite
odoo-bin -d erp_delivery_test -i erp_delivery,erp_delivery_sale,erp_delivery_quality \
  --test-enable --test-tags /erp_delivery,/erp_delivery_sale,/erp_delivery_quality --stop-after-init

# 4 combinations + 2 thứ tự cài (DoD Milestone 5)
createdb erp_combo_core;                 -i erp_delivery
createdb erp_combo_core_sale;             -i erp_delivery,erp_delivery_sale
createdb erp_combo_core_quality;          -i erp_delivery,erp_delivery_quality
createdb erp_combo_all3_sale_first;       -i erp_delivery,erp_delivery_sale,erp_delivery_quality
createdb erp_combo_all3_quality_first;    -i erp_delivery,erp_delivery_quality,erp_delivery_sale

# Upgrade + uninstall round-trip (odoo-bin shell): uninstall quality rồi
# sale, xác nhận erp_delivery vẫn hoạt động ở mỗi bước.

# Lint
python3 -m pylint --load-plugins=pylint_odoo -d all -e odoolint custom_addons/erp_delivery custom_addons/erp_delivery_sale custom_addons/erp_delivery_quality
```

### Result

**PASS**

- `erp_delivery_quality` alone: `0 failed, 0 error(s) of 4 tests` +
  `test_cooperative` **skipped** (đúng hành vi mong đợi — thiếu
  `erp_delivery_sale`), log: `skipped setUpClass (...TestCooperativeValidation)
  : Both erp_delivery_sale and erp_delivery_quality must be installed for
  this test.`
- Cả 3 addon cùng cài: `0 failed, 0 error(s) of 39 tests` — bao gồm
  `test_cooperative::test_both_validations_run_and_compose` **chạy thật**
  (không skip), xác nhận log `Starting
  TestCooperativeValidation.test_both_validations_run_and_compose`.
- 5 combination install (`core`, `core+sale`, `core+quality`,
  `all3` thứ tự sale→quality, `all3` thứ tự quality→sale): **cả 5 đều
  `EXIT=0`**, không ERROR/CRITICAL (ngoài RST warning không liên quan đã
  xác nhận từ Sprint 1).
- Upgrade (`-u erp_delivery,erp_delivery_sale,erp_delivery_quality`): exit
  code 0.
- Uninstall tuần tự (`erp_delivery_quality` → `erp_delivery_sale`, qua
  `odoo-bin shell`, chạy thật):
  ```
  after uninstalling erp_delivery_quality: erp_delivery_quality state=uninstalled, erp_delivery state=installed
  after uninstalling erp_delivery_sale: erp_delivery_sale state=uninstalled, erp_delivery state=installed
  erp_delivery still functional after both optional addons removed: True
  ```
- `pylint-odoo` (`-e odoolint`, cả 3 addon): **9.96/10** — chỉ còn 3 cảnh
  báo `manifest-required-author` (1 mỗi addon), quy ước OCA đã chấp nhận từ
  Sprint 1. `missing-readme` đã hết hẳn (thêm `README.md` mỗi addon ở
  Sprint 5D).

**NOT EXECUTED**

- Benchmark `--log-sql` theo đúng nghĩa đen "1000 project" qua UI thật —
  không có browser. Thay bằng test đo `sql_log_count` ở quy mô 150-300
  record (đã thiết lập từ Sprint 3, giữ nguyên nguyên tắc ở Sprint 5).
- Demo data đầy đủ theo checklist cuối (2 companies, 3 customers, 5
  solutions, 3 projects, 6 module lines, 10 tasks, 2 SO, 3 users) — **không
  nằm trong chỉ thị "chỉ thực hiện phạm vi Sprint 5"** của người dùng cho
  task này; đây thuộc `demo/` data mà Sprint 1 mục 2.5.4 đã liệt kê nhưng
  chưa task nào trong 5 sprint yêu cầu cụ thể tạo nó — ghi vào Known
  Limitations, không tự thêm ngoài phạm vi được giao.

## 11. Technical Decisions

### Decision

Bridge case check dùng `"erp_sale_order_id" in self._fields` thay vì
`'sale.order' in self.env` như code sketch gốc của plan.

### Reason

Xem `TECHNICAL_NOTES.md` mục 3 — tóm tắt: `'sale.order' in self.env` chỉ
xác nhận app Sales (model `sale.order`) có trong registry, không xác nhận
addon `erp_delivery_sale` (nguồn duy nhất của field `erp_sale_order_id`)
đã cài. Một instance cài `sale_management` mà không cài `erp_delivery_sale`
sẽ làm `'sale.order' in self.env` = True nhưng `self.sale_order_id`/
`self.erp_sale_order_id` không tồn tại → `AttributeError`. Kiểm tra field
tồn tại trong `self._fields` là điều kiện CHÍNH XÁC.

### Alternative considered

1. Giữ `'sale.order' in self.env` như plan → **loại**: không chính xác,
   rủi ro crash khi cài `sale`/`sale_management` đơn lẻ không có
   `erp_delivery_sale`.
2. `try/except AttributeError` quanh truy cập field → **loại**: che giấu
   lỗi, không rõ ràng, không idiomatic.
3. **Chọn**: `"erp_sale_order_id" in self._fields`.

### Why rejected

Phương án 1 là lỗi logic tiềm ẩn thực sự (không phải giả định) — phương án
2 là anti-pattern che lỗi thay vì kiểm tra điều kiện đúng.

---

### Decision

Đổi label field `res.partner.company_currency_id` từ "Currency" thành "ERP
Subscription Currency".

### Reason

Khi test 4 combination cài đặt (DoD Milestone 5), log thực tế xuất hiện
warning:
```
Two fields (company_currency_id, currency_id) of res.partner() have the
same label: Currency. [Modules: erp_delivery and account]
```
Nguyên nhân xác nhận: `sale` (được `sale_management` kéo theo) depend
`account_payment` → `account`; khi đó `account` module thêm field
`currency_id` (label "Currency") lên `res.partner`, trùng label với field
kỹ thuật của ta. Đây là warning, không phải lỗi, nhưng gây nhầm lẫn UX (2
field "Currency" khác nhau hiển thị cùng tên). Đổi label sang cụ thể hơn
giải quyết triệt để mà không đổi hành vi field.

### Alternative considered

Không có — đây là fix 1 dòng, không có trade-off đáng kể.

### Why rejected

N/A.

---

### Decision

`env.norecompute()` (Sprint 5B điểm 5 của plan) **không được triển khai**
— không viết code cho API không tồn tại.

### Reason

`grep -rn "norecompute" odoo/api.py odoo/models.py` trong source Odoo 18
thực tế: **không có kết quả**. API này không tồn tại trong framework.
nguyên tắc kỹ thuật của dự án ("Không được tự chế API/framework
behavior") áp dụng trực tiếp. Hành vi thực tế tương đương (ORM tự batch
recompute trong 1 transaction khi dùng `@api.model_create_multi`) đã có sẵn
và đã được verify bằng test đo query count thật từ Sprint 3
(`test_bulk_module_line_create_and_aggregate`), tiếp tục PASS ở Sprint 5.

### Alternative considered

1. Viết 1 context manager giả lập tên `norecompute` (chỉ để "có code khớp
   plan") → **loại**: tạo API giả, gây hiểu nhầm cho dev đọc sau, không có
   tác dụng thực (ORM đã tự làm việc này).
2. **Chọn**: không viết, ghi rõ trong `TECHNICAL_NOTES.md` + tài liệu này
   rằng đây là hành vi mặc định của ORM Odoo 18, có test chứng minh.

### Why rejected

Phương án 1 vi phạm trực tiếp nguyên tắc "không tự chế framework behavior".

## 12. Known Limitations

- Demo data đầy đủ (2 companies, 3 customers, 5 solutions, 3 projects, 6
  module lines, 10 tasks, 2 SO, 3 users) theo checklist mục 6.1 của plan —
  **chưa tạo**, vì không nằm trong chỉ thị "chỉ thực hiện phạm vi Sprint 5"
  của người dùng cho lần thực hiện này (không phải 1 trong các mục được
  liệt kê rõ: tạo addon quality, test tổ hợp, performance audit, test
  scenario, TECHNICAL_NOTES, docs). Nếu cần, đây là việc độc lập, không ảnh
  hưởng tính đúng đắn của code hiện có.
- Chưa test UI qua trình duyệt thật (không có browser trong môi trường
  này) — bù bằng toàn bộ view XML đã parse/install thành công qua 5
  combination, và mọi logic nghiệp vụ test qua ORM trực tiếp.
- `pylint-odoo` còn 3 warning `manifest-required-author` (quy ước OCA,
  không áp dụng dự án nội bộ) — chấp nhận từ Sprint 1, nhất quán xuyên suốt
  5 sprint.

## 13. Next Step

Dự án đã hoàn thành đủ 5 sprint theo `ERP_Delivery_Execution_Plan.md`. Các
hướng mở rộng hợp lý tiếp theo (ngoài phạm vi 5 sprint đã giao):
seed demo data đầy đủ, viết report/wizard (menu đề cập ở cấu trúc repo mục
6.3 nhưng không có task cụ thể nào trong 5 sprint yêu cầu), hoặc chuẩn bị
`Makefile`/CI pipeline cho 4 combination test tự động hoá.
