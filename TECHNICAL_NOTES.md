# Technical Notes

Giải trình kỹ thuật toàn bộ dự án ERP Delivery (Sprint 1–5), theo cấu trúc
yêu cầu ở `ERP_Delivery_Execution_Plan.md` mục 6.2 và Sprint 5D. Tài liệu
này là bản tóm tắt tổng hợp — chi tiết đầy đủ từng quyết định kỹ thuật nằm
trong `docs/implementation/00N_*.md` tương ứng, được tham chiếu ở mỗi mục.

## 1. 12 Câu hỏi Giải trình Kỹ thuật của Đề

| # | Câu hỏi | Câu trả lời |
|---|---|---|
| 1 | Bao nhiêu addon? Dependency? | 3 addon: `erp_delivery` (core, bắt buộc; depend `base, mail, project, contacts`), `erp_delivery_sale` (tùy chọn; depend `erp_delivery, sale_management`), `erp_delivery_quality` (tùy chọn; depend **chỉ** `erp_delivery`, không depend sale). Xem sơ đồ ở `README.md` gốc. |
| 2 | Model chuẩn nào được kế thừa? | `res.partner`, `project.project`, `project.task`, `project.milestone`, `sale.order`. **Khác với dự kiến ban đầu của đề**: `project.milestone` cũng được kế thừa (`_inherit`) thay vì tạo `erp.milestone` mới — Odoo 18 đã có model chuẩn tương đương (xem mục 3 dưới và `docs/implementation/003_...md` mục 11, ADR-010). |
| 3 | Data nào stored, data nào dynamic? | **Stored**: toàn bộ 10 computed field dùng cho list/dashboard (`module_count`, `total_planned_effort`, `total_actual_effort`, `mandatory_task_count`, `mandatory_done_count`, `progress_percent`, `customer_code`, `duration_days`, `health_status`, `erp.project.module.line.actual_effort`) + `quality_score` (Sprint 5). `health_status` **bắt buộc index**. **Dynamic/không-store**: `is_erp_ready` (sale.order), `is_quality_gate_passed`, `company_currency_id` (res.partner, kỹ thuật) — chỉ dùng trong 1 form, không cần search/filter/group_by nhanh. Xem `docs/implementation/003_...md` mục 4. |
| 4 | Field vừa computed vừa cho user nhập? | Pattern `compute` + `inverse`: `duration_days` trên `project.project` (nhập số ngày → tự set lại `planned_go_live = date_start + N ngày`), dùng `fields.Date.add()` để đảm bảo idempotent. Xem `docs/implementation/003_...md` mục 4. |
| 5 | Bảo vệ quyền ở lớp nào? | **Groups** (`erp_delivery.group_erp_delivery_{user,consultant,manager}`, menu/action visibility) → **Model access** (`ir.model.access.csv`, riêng cho từng model, không dùng `implied_ids` kéo quyền `project.group_project_*` chuẩn — xem ADR-009) → **Record rules** (`ir.rule`, scope theo `project_id.is_erp_delivery`/`user_id`/`member_ids`/`company_id`) → **Field-level** (`groups=` trên `internal_cost`, `subscription_value`, `contract_value`, `note_internal`, `quality_threshold`) → **SQL constraints** (`UNIQUE` trên `erp_code`, `erp.solution.code`, `(project_id, solution_id)`, `erp_sale_order_id`, `(project_id, criterion_id)`). |
| 6 | User nhiều group → quyền cuối? | `implied_ids`: Manager ⊃ Consultant ⊃ User. Khi 1 user thuộc cả Consultant và Manager (qua implied), Odoo OR domain của TẤT CẢ rule mà user thuộc group — xem `docs/implementation/002_...md` mục 7. Record rule của Manager (company-wide) rộng hơn Consultant (own-project) nên kết quả cuối = quyền Manager (OR không làm hẹp lại). |
| 7 | Multi-company & cross-company? | `erp.solution.internal_cost`: `company_dependent=True` (Float, không phải Monetary — xem câu hỏi ngoài lề ở mục 2 ADR-002). Record rule `company_id in company_ids` (không dùng `company_id` đơn — bẫy phổ biến). Test: `tests/test_multicompany.py` (`test_no_data_leak_between_companies`, `test_internal_cost_differs_between_companies`) — chạy thật, PASS. |
| 8 | Cooperative inheritance Go-live? | `_check_go_live_conditions()` trên `project.project` (định nghĩa ở `erp_delivery`) trả về **list** blocker, không raise trực tiếp. `erp_delivery_quality` override: gọi `super()._check_go_live_conditions()` **đầu tiên**, rồi `.append()` blocker Quality Score. `action_go_live()` gọi method này, raise `UserError` duy nhất 1 lần với TẤT CẢ blocker (không dừng ở blocker đầu). Xem mục 2 dưới. |
| 9 | Logic khi 2 addon optional cùng cài? | Runtime check trong `erp_delivery_quality`: **`'erp_sale_order_id' in self._fields`** — không phải `'sale.order' in self.env` như code sketch gốc của đề. Lý do: `'sale.order' in self.env` chỉ xác nhận app Sales (model `sale.order`) có tồn tại trong registry, **không** xác nhận addon `erp_delivery_sale` (nguồn gốc thật của field `erp_sale_order_id`) đã cài — một instance có thể cài `sale`/`sale_management` mà không cài `erp_delivery_sale`. Dùng field-existence check chính xác hơn và tránh `AttributeError`. Xem mục 3 dưới. |
| 10 | 3 vị trí N+1 và cách xử lý? | (a) List project: toàn bộ field hiển thị đều `store=True` → 1 query SQL duy nhất cho list view, không cần tính lại. (b) Dashboard aggregate: `get_health_status_dashboard_data()` — 1 lệnh `_read_group` (vì `health_status` đã stored+indexed, Odoo tự làm `GROUP BY` SQL, không cần code tay). (c) Bulk import: `@api.model_create_multi` (bắt buộc từ Odoo 15+, đã dùng cho `project.project.create()`) — ORM Odoo 18 tự động batch/defer recompute trong 1 transaction, **không có** API `env.norecompute()` như code sketch của đề (API không tồn tại trong Odoo 18 thực tế — xem mục 4 dưới). Cả 3 điểm đều có test đo query count thật, PASS. |
| 11 | Index cho data nào và vì sao? | `health_status` (bắt buộc, filter theo tình trạng sức khỏe), `state`, `code`, `is_erp_delivery`, `planned_go_live`, `partner_id`, `user_id` (ERP PM — thêm ở Sprint 5B) trên `project.project`; `erp_code`, `is_erp_customer` trên `res.partner`; `UNIQUE(project_id, solution_id)` trên `erp.project.module.line` (unique constraint tự tạo composite index). Tất cả đều là field dùng trong search/filter/record-rule mặc định. |
| 12 | Test cài riêng/kết hợp thế nào? | 4 tổ hợp đã cài và test thật trên DB riêng: core / core+sale / core+quality / cả 3 (2 thứ tự cài khác nhau: sale trước quality và ngược lại) — xem mục 10 "Validation Result" của `docs/implementation/005_...md`. Không dùng Makefile (không có trong scope task được giao) — chạy trực tiếp qua `odoo-bin -i <modules> --test-enable --test-tags <tags>` trên từng DB PostgreSQL riêng. |

## 2. Cooperative Inheritance Pattern (Go-live)

```python
# erp_delivery/models/project_project.py
def _check_go_live_conditions(self):
    self.ensure_one()
    blockers = []
    if not self.partner_id: blockers.append(...)
    if not self.user_id: blockers.append(...)            # ERP PM
    if not self.module_line_ids: blockers.append(...)
    mandatory_undone = self.tasks.filtered(lambda t: t.is_mandatory and not t.is_closed)
    if mandatory_undone: blockers.append(...)
    critical_open_risks = self.risk_ids.filtered(lambda r: r.level == "critical" and r.state == "open")
    if critical_open_risks: blockers.append(...)
    if not self.planned_go_live or self.planned_go_live < fields.Date.today():
        blockers.append(...)
    return blockers                       # <-- LIST, không raise

def action_go_live(self):
    for project in self:
        blockers = project._check_go_live_conditions()
        if blockers:
            raise UserError(...)          # <-- raise 1 lần, ở caller
        project._erp_transition("ready", "go_live", {...})
```

```python
# erp_delivery_quality/models/project_project.py
def _check_go_live_conditions(self):
    blockers = super()._check_go_live_conditions()      # <-- CRITICAL: gọi trước
    if self.quality_score < self.quality_threshold:
        blockers.append(...)
    if "erp_sale_order_id" in self._fields and self.erp_sale_order_id:
        if self.contract_value < self.erp_sale_order_id.amount_total * 0.95:
            blockers.append(...)
    return blockers
```

**Vì sao trả về list thay vì raise ngay**: cho phép mọi addon trong chuỗi
kế thừa (ở đây chỉ có `erp_delivery_quality`, nhưng thiết kế mở cho addon
khác trong tương lai) tự do append blocker của mình, và chỉ CALLER cuối
cùng (`action_go_live`) quyết định khi nào raise — với TOÀN BỘ blocker từ
mọi addon cùng lúc, không chỉ blocker đầu tiên gặp phải. Test
`erp_delivery_quality/tests/test_cooperative.py::test_both_validations_run_and_compose`
xác nhận cả 2 message ("Quality Score" và "Contract value discrepancy")
cùng xuất hiện trong 1 `UserError` khi cả 2 addon cùng cài — chạy thật,
PASS.

**Thứ tự cài không ảnh hưởng kết quả**: vì cơ chế này dựa trên Python MRO
(Method Resolution Order) của Odoo — khi addon B kế thừa (`_inherit`) model
mà addon A cũng kế thừa, Odoo xây class cuối cùng theo thứ tự nạp module
(load order dựa trên dependency graph, không phải thứ tự người dùng gõ lệnh
`-i`), và `super()` luôn đi đúng theo chain đó bất kể gõ `-i
erp_delivery_sale,erp_delivery_quality` hay `-i
erp_delivery_quality,erp_delivery_sale`. Đã verify thật bằng cách cài cả 3
addon theo 2 thứ tự khác nhau trên 2 DB riêng — xem `docs/implementation/
005_...md` mục 10.

## 3. Bridge Case — 2 addon optional cùng cài

`erp_delivery_quality` **không** depend `erp_delivery_sale` (và ngược lại
`erp_delivery_sale` không depend `erp_delivery_quality`) — không có bridge
module riêng (giới hạn tối đa 3 addon). Khi cả 2 cùng cài, check thương mại
bổ sung được thực hiện bằng **field-existence check**:

```python
if "erp_sale_order_id" in self._fields and self.erp_sale_order_id:
    ...
```

**Khác với code sketch gốc của đề** (`if 'sale.order' in self.env and
self.sale_order_id:`) — lý do: `'sale.order' in self.env` chỉ chứng minh
app Sales (model `sale.order`) tồn tại trong registry, không chứng minh
addon `erp_delivery_sale` đã cài. Field `erp_sale_order_id` chỉ tồn tại
trên `project.project` khi **chính** `erp_delivery_sale` được cài (đó là
addon duy nhất định nghĩa field này) — kiểm tra field tồn tại trong
`self._fields` là điều kiện CHÍNH XÁC cho "addon kia có cài hay không",
tránh `AttributeError` nếu ai đó cài `sale`/`sale_management` riêng lẻ mà
không có `erp_delivery_sale`. Chi tiết: `docs/implementation/
005_quality_gate_performance_docs.md` mục 11.

## 4. 3 Điểm Tối ưu Performance + Trade-off

| # | Điểm tối ưu | Cách làm | Trade-off |
|---|---|---|---|
| 1 | N+1 trên list view | Toàn bộ field hiển thị list (`module_count`, `progress_percent`, `total_actual_effort`, `health_status`, ...) đều `store=True` → 1 query SQL/list load | Tốn chi phí recompute mỗi lần task/module_line thay đổi; chấp nhận vì tỉ lệ read:write rất cao trong nghiệp vụ theo dõi dự án |
| 2 | Dashboard aggregate | `health_status` đã stored+indexed → `_read_group` CHUẨN của Odoo tự sinh `GROUP BY` SQL, không cần code tay. `get_health_status_dashboard_data()` là entry point cho dashboard, bọc 1 lệnh `_read_group` duy nhất | Không có — đây chính là cách đúng của Odoo khi field đã stored; viết SQL tay thêm sẽ là code thừa (vi phạm "không tạo code thừa nếu Odoo đã có cơ chế chuẩn") |
| 3 | Prefetch module_line + task | Dùng `projects.mapped('module_line_ids.task_ids.name')` (1 lệnh, nhiều project) thay vì loop lồng 3 cấp `for p / for ml / for t` | Không — `mapped()` là API chuẩn ORM, prefetch tự động theo batch |
| 4 | Index bổ sung | Xem câu hỏi #11 ở trên | Tốn thêm dung lượng index trên disk (không đáng kể so với lợi ích query) |
| 5 | Bulk import / batch create | `@api.model_create_multi` — Odoo 18 ORM tự batch/defer recompute trong 1 transaction, không cần context manager đặc biệt | **Lưu ý quan trọng**: code sketch của đề (`with self.env.norecompute(): ...`) tham chiếu một API **không tồn tại trong Odoo 18** (`grep -rn "norecompute" odoo/api.py odoo/models.py` → không có kết quả). Đây là hành vi MẶC ĐỊNH của ORM hiện đại — không viết thêm code "giả API" theo nguyên tắc không tự chế API/framework behavior. Đã verify bằng test đo query count thật (`test_bulk_module_line_create_and_aggregate`, `test_prefetch_via_mapped_across_many_projects`) — PASS, không scale tuyến tính theo số record |

Toàn bộ 5 điểm đều có test tự động đo **số lượng SQL query** (không phải
suy luận lý thuyết) trong `erp_delivery/tests/test_project_performance.py`
— xem kết quả thật ở `docs/implementation/005_...md` mục 10.

## 5. Tổng hợp các điểm xung đột giữa đề và Odoo 18 thực tế đã xử lý

Danh sách đầy đủ ADR (Architecture Decision Record) trong
`docs/IMPLEMENTATION_STATUS.md`. Tóm tắt các trường hợp Odoo 18 **không**
khớp với code sketch/giả định của execution plan — mỗi trường hợp đều được
audit bằng cách đọc source code `odoo/` thật, không suy đoán:

1. `Monetary` không được phép `company_dependent=True` (Sprint 1, ADR-002).
2. `res.partner` không có field `currency_id` sẵn (Sprint 1, ADR-003).
3. `project.project.task_ids` có domain ẩn loại bỏ task đã đóng — phải dùng
   field `tasks` (không domain) cho mọi phép tính completion (Sprint 3,
   ADR-012) — **phát hiện qua 1 test thất bại thực tế**, không phải suy
   luận trước.
4. `project.task.effective_hours`/`progress` chỉ có khi cài `hr_timesheet`
   (ngoài kiến trúc 3-addon đã thống nhất) — Sprint 3, ADR-011.
5. `project.milestone` đã là model chuẩn của Odoo 18 — không cần tạo
   `erp.milestone` mới (Sprint 3, ADR-010).
6. Addon chuẩn `sale_project` đã định nghĩa `project.project.sale_order_id`
   với ngữ nghĩa khác — đổi tên field của ta thành `erp_sale_order_id`
   (Sprint 4, ADR-013).
7. `env.norecompute()` không tồn tại trong Odoo 18 (Sprint 5, mục 4 trên).
8. `'sale.order' in self.env` không phải điều kiện chính xác để phát hiện
   addon `erp_delivery_sale` — dùng field-existence check thay thế
   (Sprint 5, mục 3 trên).

Mỗi trường hợp đều được xử lý theo nguyên tắc kiểm chứng framework: xác định
điểm xung đột → kiểm tra cách
chuẩn của Odoo 18 (đọc source thật) → ưu tiên triển khai an toàn, đúng
framework → ghi rõ requirement ban đầu/vấn đề/cách triển khai cuối/lý
do/ảnh hưởng trong Markdown — không âm thầm chọn 1 bên.
