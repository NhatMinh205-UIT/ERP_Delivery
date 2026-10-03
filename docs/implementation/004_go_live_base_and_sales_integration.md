# Go-live Base Workflow & Sales Integration (Sprint 4 — Tuần 7–8)

## 1. Mục tiêu

**Sprint 4A** (trong `erp_delivery`): `_check_go_live_conditions()` hook —
foundation cho cooperative inheritance mà Quality Gate (Sprint 5) sẽ mở
rộng — và tích hợp vào `action_go_live()`.

**Sprint 4B**: addon `erp_delivery_sale` — tạo ERP Delivery Project từ Sale
Order đã xác nhận, cài đặt/gỡ cài đặt độc lập với `erp_delivery_quality`.

## 2. Requirement liên quan

`ERP_Delivery_Execution_Plan.md`, mục 3 — **Sprint 4 (Tuần 7–8): Sales
Integration + Go-live Base**.

## 3. Trạng thái trước khi thay đổi

Audit lại toàn bộ Sprint 1–3 trước khi code (theo yêu cầu):

- `erp_delivery`: `res.partner`, `erp.solution`/`category`,
  `project.project` (8-state machine, `code`, `member_ids`,
  `planned_go_live`, `actual_go_live`, `contract_value`, `note_internal`,
  **10 computed field** đã xác nhận đủ — `module_count`,
  `total_planned_effort`, `total_actual_effort`, `mandatory_task_count`,
  `mandatory_done_count`, `progress_percent`, `customer_code`,
  `duration_days`, `health_status` trên `project.project`, và
  `actual_effort` trên `erp.project.module.line`), `project.task`
  extension, `project.milestone` extension, `erp.risk`, cron daily health
  recompute. 22 → 26 test (sau khi thêm 4 test go-live) đều PASS trước khi
  bắt đầu Sprint 4B.
- `action_go_live()` (Sprint 2) trước đây **chỉ** transition state
  `ready → go_live`, không có kiểm tra điều kiện — đúng như đã ghi chú rõ
  trong code lúc đó ("Sprint 2 scope is the plain state transition only").
- `custom_addons/erp_delivery_sale/` hoàn toàn rỗng.

### Audit kết quả — phát hiện xung đột quan trọng với Odoo 18 chuẩn

**`sale_project` (addon chuẩn riêng, KHÔNG phải `sale_management`) đã định
nghĩa `project.project.sale_order_id`** (`addons/sale_project/models/
project_project.py` dòng 35: `sale_order_id = fields.Many2one(related=
'sale_line_id.order_id')`) — một field **related, không unique, ngữ nghĩa
hoàn toàn khác** với field `sale_order_id` (Many2one thường + SQL UNIQUE
constraint) mà execution plan mục Sprint 4B yêu cầu. `sale_project` có
`auto_install: ['sale_management', 'project_account']` — nó tự cài khi CẢ
`sale_management` VÀ `project_account` cùng có mặt trong hệ thống (ví dụ khi
cài thêm phân hệ Kế toán/Invoicing vào một instance đã có Sales+Project).
`erp_delivery_sale` không khai báo depend `sale_project`, nên không có xung
đột CỨNG ngay lúc này, nhưng nếu 2 module khác nhau định nghĩa field CÙNG
TÊN với kiểu khác nhau trên cùng model, đây là tình huống dễ vỡ, phụ thuộc
vào tổ hợp addon nào khác được cài trên instance — không kiểm soát được từ
phía addon này. Xem Technical Decision ở mục 11.

## 4. Thiết kế

### 4A — `_check_go_live_conditions()` (trong `erp_delivery`)

```python
def _check_go_live_conditions(self):
    self.ensure_one()
    blockers = []
    if not self.partner_id: blockers.append(...)
    if not self.user_id: blockers.append(...)          # ERP PM — xem 4.2
    if not self.module_line_ids: blockers.append(...)
    mandatory_undone = self.tasks.filtered(...)         # xem 4.3
    if mandatory_undone: blockers.append(...)
    critical_open_risks = self.risk_ids.filtered(...)
    if critical_open_risks: blockers.append(...)
    if not self.planned_go_live or self.planned_go_live < fields.Date.today():
        blockers.append(...)
    return blockers
```

6 điều kiện cụ thể (đề mô tả khái quát là "5 điều kiện lõi" nhưng liệt kê
6 `if`-block trong code sketch gốc — giữ nguyên đủ 6 theo đúng code, không
bớt điều kiện nào):

1. `partner_id` bắt buộc.
2. ERP Project Manager (`user_id`) bắt buộc.
3. Ít nhất 1 module line.
4. Không còn task mandatory chưa đóng.
5. Không còn risk critical đang mở.
6. `planned_go_live` hợp lệ (có giá trị và không ở quá khứ).

`action_go_live()` (đã có từ Sprint 2) được cập nhật: gọi
`_check_go_live_conditions()` trước, raise `UserError` liệt kê toàn bộ
blocker nếu còn, chỉ sau đó mới gọi `_erp_transition("ready", "go_live", ...)`
— giữ nguyên validate thứ tự state machine đã có từ Sprint 2, cộng thêm lớp
điều kiện nghiệp vụ mới.

**Method trả về LIST** (không raise trực tiếp bên trong) — đúng thiết kế
hook/extension point mà plan yêu cầu: Quality Gate (Sprint 5) sẽ override,
gọi `super()._check_go_live_conditions()` trước rồi `.append()` blocker của
riêng nó.

### 4B — Addon `erp_delivery_sale`

| Model | Kỹ thuật | Field mới |
|---|---|---|
| `sale.order` | `_inherit` | `erp_project_id` (M2o project.project, readonly, copy=False), `is_erp_ready` (compute: `state == 'sale' and not erp_project_id`) |
| `project.project` | `_inherit` | `erp_sale_order_id` (M2o sale.order, readonly, copy=False) — **đổi tên từ `sale_order_id`**, xem Technical Decisions |

SQL constraint `UNIQUE(erp_sale_order_id)` trên `project.project` — ưu tiên
hơn Python check để tránh race condition (đúng lý do plan đã nêu).

`action_create_erp_project()` trên `sale.order`:
1. Guard Python: nếu `erp_project_id` đã có → `UserError`.
2. Tạo `project.project` với `is_erp_delivery=True`, đồng bộ `partner_id`,
   `contract_value = amount_total`, `erp_sale_order_id`, `company_id`.
3. `project.message_post(...)` — post message tham chiếu SO nguồn (DoD yêu
   cầu rõ "Chatter project mới tạo có message reference SO nguồn" — code
   sketch gốc của plan KHÔNG có dòng này, phải tự thêm để đáp ứng DoD).
4. Gán ngược `self.erp_project_id`.
5. Trả về action mở form project vừa tạo.

Smart button 2 chiều: `sale.order.action_view_erp_project()` và
`project.project.action_view_erp_source_sale_order()`.

## 5. Files thay đổi

**`erp_delivery`**

| File | Thay đổi |
|---|---|
| `models/project_project.py` | Thêm `_check_go_live_conditions()`, cập nhật `action_go_live()` |
| `tests/test_go_live.py` | Mới (4 test) |
| `tests/test_project_workflow.py` | Cập nhật `test_full_state_sequence` để thêm module line trước khi gọi `action_go_live()` (nếu không sẽ fail do blocker mới) |
| `tests/__init__.py` | Thêm import |

**`erp_delivery_sale`** (toàn bộ mới)

| File | |
|---|---|
| `__manifest__.py`, `__init__.py` | |
| `models/__init__.py`, `models/project_project.py`, `models/sale_order.py` | |
| `views/sale_order_views.xml`, `views/project_project_views.xml` | |
| `tests/__init__.py`, `tests/test_sales_integration.py` | 5 test |

## 6. Giải thích implementation

```
Sales confirm SO (action_confirm — chuẩn Odoo, không đụng tới)
    ↓
is_erp_ready = True (state=='sale' và chưa có erp_project_id)
    ↓
Nút "Create ERP Project" xuất hiện trên header SO form
    ↓
action_create_erp_project(): tạo project.project (is_erp_delivery=True,
    partner_id/contract_value đồng bộ từ SO, erp_sale_order_id=SO.id)
    ↓
SQL UNIQUE(erp_sale_order_id) đảm bảo 1 SO chỉ sinh ra 1 project
    ↓
Chatter project mới có message "Project created from Sale Order SxxxxX"
    ↓
Smart button "ERP Project" (trên SO) / "Source Sale Order" (trên project)
    điều hướng 2 chiều
```

```
Project ở state 'ready', PM bấm "Go-Live"
    ↓
action_go_live() gọi _check_go_live_conditions()
    ↓
Nếu còn blocker (thiếu PM, thiếu module, mandatory task chưa xong,
risk critical còn mở, planned_go_live không hợp lệ) → UserError liệt kê
TẤT CẢ blocker cùng lúc (không dừng ở blocker đầu tiên)
    ↓
Nếu không còn blocker → _erp_transition("ready", "go_live", ...) như Sprint 2
```

## 7. Security

- Không có model mới trong `erp_delivery_sale` → không cần ACL mới.
  `sale.order` dùng ACL chuẩn của `sale_management`/`sale`; `project.project`
  dùng ACL đã thiết lập ở `erp_delivery` (Sprint 2).
- `erp_sale_order_id`/`erp_project_id` đều `readonly=True` trên form — chỉ
  set được qua action method, không cho user sửa tay trực tiếp (tránh gán
  sai liên kết SO↔Project).

## 8. Performance

- Không có computed/aggregate field mới trong Sprint 4 — không cần đánh giá
  N+1 thêm. `action_create_erp_project()` tạo 1 project + 1 message post,
  không có vòng lặp.

## 9. Tests

**`test_go_live.py`** (4 test, Sprint 4A)

| Test | Scenario | Expected |
|---|---|---|
| `test_blocked_when_nothing_is_set` | Project rỗng (không partner/PM/module/ngày) | 4 blocker, `action_go_live()` raise `UserError` |
| `test_blocked_by_mandatory_task_and_critical_risk` | Project đủ điều kiện khác, nhưng có 1 mandatory task chưa xong + 1 risk critical mở | 2 blocker đúng nội dung, raise `UserError`, state không đổi |
| `test_go_live_succeeds_when_all_conditions_met` | Project đủ mọi điều kiện, đi qua đủ state machine tới `ready` | `_check_go_live_conditions()` rỗng, `action_go_live()` thành công, state=`go_live`, `actual_go_live`=hôm nay |
| `test_mandatory_task_blocker_clears_once_task_closed` | Đóng task mandatory còn lại | Blocker biến mất, go-live thành công |

**`test_sales_integration.py`** (5 test, Sprint 4B — unit test 16–19 của đề
+ 1 test DoD)

| Test | Scenario | Expected |
|---|---|---|
| `test_full_workflow_so_to_erp_project` (unit test 16) | SO confirm → tạo project, chỉ cài `erp_delivery_sale` (không có quality) | `erp_project_id` set, `is_erp_delivery=True`, `is_erp_ready` tắt |
| `test_second_project_from_same_order_raises_integrity_error` (unit test 17) | Gọi `action_create_erp_project()` lần 2 (Python guard); tạo trực tiếp project thứ 2 trỏ cùng SO (bỏ qua guard, mô phỏng race condition) | Python guard → `UserError`; tạo trực tiếp → `IntegrityError` (SQL constraint) |
| `test_partner_and_contract_value_synced_on_creation` (unit test 18) | SO 3 sản phẩm, confirm, tạo project | `project.partner_id == order.partner_id`, `project.contract_value == order.amount_total` |
| `test_smart_buttons_navigate_both_ways` (unit test 19) | Gọi `action_view_erp_project()` và `action_view_erp_source_sale_order()` | Mỗi action trỏ đúng `res_model`/`res_id` của phía bên kia |
| `test_project_chatter_references_source_order` (DoD) | Sau khi tạo project từ SO | `project.message_ids` có message chứa tên SO nguồn |

## 10. Validation Result

### Executed

```bash
createdb -h /var/run/postgresql -p 5433 erp_delivery_test

# erp_delivery alone (Sprint 4A regression + new tests)
.../odoo-bin -d erp_delivery_test ... -i erp_delivery --test-enable --test-tags /erp_delivery --stop-after-init

# Both addons together
.../odoo-bin -d erp_delivery_test ... -i erp_delivery,erp_delivery_sale \
  --test-enable --test-tags /erp_delivery,/erp_delivery_sale --stop-after-init

# Upgrade idempotency (both)
... -u erp_delivery,erp_delivery_sale --stop-after-init

# Uninstall DoD check (odoo-bin shell): create SO -> project, then
# button_immediate_uninstall() on erp_delivery_sale only, then verify
# erp_delivery still installed, project still exists, erp_sale_order_id
# field gone from the registry.

# Lint
python3 -m pylint --load-plugins=pylint_odoo -d all -e odoolint custom_addons/erp_delivery custom_addons/erp_delivery_sale
```

### Result

**PASS**

- `erp_delivery` alone: `0 failed, 0 error(s) of 26 tests` (22 cũ + 4 go-live
  mới).
- Cả 2 addon cùng cài: `0 failed, 0 error(s) of 31 tests` (26 + 5 sales
  integration).
- Upgrade (`-u erp_delivery,erp_delivery_sale`): exit code 0, không
  ERROR/CRITICAL.
- Uninstall DoD (chạy thật qua `odoo-bin shell`, không phải suy đoán):
  ```
  UNINSTALL erp_delivery_sale OK, state: uninstalled
  erp_delivery state: installed
  project still exists: project.project(179,) is_erp_delivery: True
  erp_sale_order_id field still on model: False
  ```
  Khớp chính xác yêu cầu DoD: "Uninstall erp_delivery_sale → erp_delivery
  vẫn hoạt động, project cũ vẫn còn (field sale_order_id bị xóa)".
- `pylint-odoo` (`-e odoolint`, cả 2 addon): 9.93/10 — chỉ còn 4 cảnh báo
  OCA-only (2 addon × 2 cảnh báo `manifest-required-author`/
  `missing-readme`), đã chấp nhận giữ nguyên từ Sprint 1.

**NOT EXECUTED**

- Kiểm thử UI qua trình duyệt thật (bấm nút "Create ERP Project" trên SO
  form, xem smart button 2 chiều). Môi trường không có browser — bù bằng
  view XML parse/install thành công (không lỗi xpath/field) và toàn bộ
  action method được test trực tiếp qua ORM với kết quả dict trả về đúng
  `res_model`/`res_id`.
- "Thay đổi thứ tự cài (sale trước quality vs ngược lại)" — chưa thể test
  vì `erp_delivery_quality` chưa tồn tại (Sprint 5). Sẽ test ở Sprint 5 khi
  cả 2 addon tùy chọn đã có.

## 11. Technical Decisions

### Decision

Field trên `project.project` đặt tên `erp_sale_order_id`, không phải
`sale_order_id` như trong code sketch của execution plan.

### Reason

Audit `addons/sale_project/models/project_project.py` dòng 35 cho thấy Odoo
18 có sẵn addon chuẩn `sale_project` (độc lập với `sale_management`, nhưng
`auto_install` khi cả `sale_management` và `project_account` cùng có mặt)
định nghĩa **field cùng tên** `sale_order_id` trên **cùng model**
`project.project`, nhưng với kiểu/ngữ nghĩa khác hẳn: `related=
'sale_line_id.order_id'` (không unique, suy ra từ order line được giao cho
project, không phải "SO nguồn sinh ra project này"). Nếu người dùng cài
thêm Invoicing vào instance đã có `erp_delivery_sale` + `sale_management`
+ `project`, `sale_project` có thể tự động được cài (`auto_install`), và
khi đó Odoo sẽ phát hiện 2 định nghĩa field trùng tên nhưng khác thuộc tính
cơ bản trên cùng model — đây là lỗi nạp registry khó đoán trước, phụ thuộc
hoàn toàn vào tổ hợp addon khác mà `erp_delivery_sale` không kiểm soát được.
Đổi tên field sang namespace riêng (`erp_` prefix, nhất quán với
`erp_project_id` phía `sale.order` mà plan đã đặt tên) loại bỏ hoàn toàn
rủi ro này mà không mất tính năng gì.

### Alternative considered

1. Giữ nguyên tên `sale_order_id` như plan → **loại**: rủi ro xung đột field
   với `sale_project` tùy theo tổ hợp addon khác được cài, không thể đảm
   bảo an toàn trong mọi trường hợp triển khai thực tế.
2. Thêm `erp_delivery_sale` phụ thuộc (depend) `sale_project` để dùng field
   `sale_order_id` có sẵn của nó → **loại**: `sale_project` mang theo
   `project_account`/phân hệ phân tích kế toán — vượt phạm vi 3-addon đã
   thống nhất (giống lý do loại `hr_timesheet` ở Sprint 3), và ngữ nghĩa
   field đó ("order line nào giao project") không khớp với yêu cầu đề
   ("SO nào sinh ra project này", 1-1, có UNIQUE constraint).
3. **Chọn**: đổi tên field sang `erp_sale_order_id`, độc lập hoàn toàn.

### Why rejected

Phương án 1 là rủi ro kỹ thuật âm thầm (silent, instance-dependent) — đúng
loại vấn đề mà tài liệu kỹ thuật yêu cầu chủ động phát hiện và
xử lý an toàn thay vì lờ đi. Phương án 2 lặp lại đúng sai lầm kiến trúc đã
tránh ở Sprint 3 (kéo theo phân hệ ngoài phạm vi chỉ để tái dùng 1 field).

## 12. Known Limitations

- `action_create_erp_project()` không tự động tạo `module_line_ids` từ
  `order_line` của SO — execution plan ghi rõ đây là bước "Optionally" (tuỳ
  chọn), không phải yêu cầu bắt buộc của Sprint 4B; không thêm để giữ đúng
  phạm vi tối thiểu.
- Chưa test UI qua trình duyệt thật (xem mục 10).
- Chưa test tổ hợp cài đặt với `erp_delivery_quality` (chưa tồn tại, đến ở
  Sprint 5).

## 13. Next Step

Sprint 5: addon `erp_delivery_quality` (cooperative inheritance —
`_check_go_live_conditions()` override gọi `super()` rồi append blocker
Quality Score + check thương mại nếu Sales cùng cài qua runtime check
`'sale.order' in self.env`), audit performance 3 điểm, đủ 8 test scenario
của đề, `README.md` mỗi addon + `TECHNICAL_NOTES.md` ở repo root.
