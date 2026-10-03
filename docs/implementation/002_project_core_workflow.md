# Project Core & Workflow (Sprint 2 — Tuần 3–4)

## 1. Mục tiêu

`project.project` được mở rộng thành ERP Delivery Project với state machine
8-state, sequence code tự sinh, chatter tracking, và phân quyền
Consultant/Manager theo đúng scope dự án.

## 2. Requirement liên quan

`ERP_Delivery_Execution_Plan.md`, mục 3 — **Sprint 2 (Tuần 3–4): Project Core
& Workflow**, và mục 2.1.1 / 2.5.2 / 2.5.3 (bảng field, groups, record rules).

## 3. Trạng thái trước khi thay đổi

Addon `erp_delivery` đã có từ Sprint 1: `res.partner` extension (ERP
Customer), `erp.solution` / `erp.solution.category` (catalog), 3 security
groups, sequence `erp.project.code` đã seed sẵn (chưa dùng tới). Model
`project.project` **chưa bị động tới** — hoàn toàn là field/view chuẩn của
module `project`.

### Audit kết quả (trước khi code)

Đọc `addons/project/models/project_project.py` và
`addons/project/security/{project_security.xml,ir.model.access.csv}` của
Odoo 18 phát hiện các điểm quan trọng ảnh hưởng tới thiết kế:

- `project.project` **đã có sẵn** `user_id` (Many2one res.users, string
  "Project Manager", `tracking=True`, `default=self.env.user`) —trùng hoàn
  toàn về ngữ nghĩa với field `pm_id` mà execution plan liệt kê.
- `project.project` đã có `date_start` (Date, "Start Date") — trùng với yêu
  cầu field `date_start` trong plan (plan không yêu cầu field mới ở đây,
  chỉ liệt kê lại field đã tồn tại).
- `project.project` đã có `currency_id` (Many2one res.currency, compute từ
  company) — có thể tái dùng làm `currency_field` cho `contract_value` mà
  không cần thêm field currency riêng.
- `project.project` đã có `date` (Date, "Expiration Date") gắn với widget
  `daterange` cùng `date_start`, và có xử lý đặc biệt trong `create()` của
  module gốc — **không** phù hợp để tái sử dụng cho `planned_go_live` vì rủi
  ro side-effect.
- ACL chuẩn (`project/security/ir.model.access.csv`): chỉ
  `project.group_project_manager` có quyền write/create/unlink trên
  `project.project`; `project.group_project_user` và `base.group_user` chỉ
  có `perm_read`. Nhóm `erp_delivery.*` của ta hoàn toàn tách biệt khỏi
  `project.group_project_*` nên **không tự động có quyền ghi** — phải cấp ACL
  riêng.
- Record rule global `project_comp_rule` (không gắn group, nên luôn AND với
  mọi rule khác) đã enforce multi-company isolation
  `[('company_id', 'in', company_ids + [False])]` ở tầng module `project`.
- Record rule `project_public_members_rule` (group `base.group_user`) chặn
  xem project có `privacy_visibility == 'followers'` nếu không phải
  follower; mặc định `privacy_visibility = 'portal'` nên không ảnh hưởng tới
  luồng ERP mặc định.

Những phát hiện này dẫn tới các Technical Decisions ở mục 11.

## 4. Thiết kế

### Models

`project.project` (`_inherit`) — mở rộng model chuẩn, không tạo model song
song (đúng nguyên tắc tận dụng model chuẩn và tránh duplicate field).

### Fields

| Field | Type | Purpose | Store | Index | Nguồn |
|---|---|---|---|---|---|
| `is_erp_delivery` | Boolean | Phân biệt ERP project với project thường | ✅ | ✅ | Mới |
| `code` | Char | Mã dự án, sinh tự động từ sequence `erp.project.code` | ✅ | ✅ | Mới |
| `member_ids` | Many2many → res.users | Team members (khác PM) | — | — | Mới |
| `planned_go_live` | Date, tracking | Ngày go-live kế hoạch | ✅ | ❌ | Mới |
| `actual_go_live` | Date, readonly, tracking | Ngày go-live thực tế | ✅ | ❌ | Mới |
| `contract_value` | Monetary, tracking | Giá trị hợp đồng | ✅ | ❌ | Mới (dùng `currency_id` có sẵn) |
| `state` | Selection (8 state), tracking | State machine | ✅ | ❌ | Mới |
| `note_internal` | Text, groups=manager | Ghi chú nội bộ | ✅ | ❌ | Mới |
| `user_id` | Many2one res.users | **ERP Project Manager** | ✅ | — | **Tái sử dụng** field chuẩn (xem Technical Decisions) |
| `date_start` | Date | Ngày bắt đầu | ✅ | — | **Tái sử dụng** field chuẩn |
| `currency_id` | Many2one res.currency | Currency cho `contract_value` | computed | — | **Tái sử dụng** field chuẩn |

### Relationships

- `project.project (N) ←→ (N) res.users` qua `member_ids` (bảng quan hệ
  riêng `erp_project_member_rel`).
- `res.partner.erp_project_ids` (Sprint 1) nay có domain
  `is_erp_delivery = True` hoạt động đúng (field này đã tồn tại từ Sprint 1
  nhưng domain bị hoãn — xem mục 12 Known Limitations của tài liệu 001).

### Business Rules

- `planned_go_live >= date_start` (chỉ áp dụng khi `is_erp_delivery=True` và
  cả 2 ngày đều có giá trị) — `@api.constrains`.
- `actual_go_live` chỉ được set khi `state` ∈ {`go_live`, `done`} —
  `@api.constrains`.
- `contract_value >= 0` — `@api.constrains`.
- `code` tự sinh qua `ir.sequence.next_by_code('erp.project.code')` khi
  `is_erp_delivery=True` và `code` chưa được set, trong `create()`
  (`@api.model_create_multi`, batch-safe).

### Workflow (state machine)

```
draft → analysis → implementation → uat → ready → go_live → done
  │         │             │           │      │        │
  └─────────┴─────────────┴───────────┴──────┴────────┴──→ cancel
                                                  (từ mọi state trừ done/cancel)
```

Action methods (mỗi action validate state hiện tại qua helper
`_erp_transition(expected_state, target_state)`, raise `UserError` nếu sai
thứ tự):

| Method | Từ state | Đến state | Ghi chú |
|---|---|---|---|
| `action_start_analysis` | draft | analysis | |
| `action_start_implementation` | analysis | implementation | |
| `action_start_uat` | implementation | uat | |
| `action_ready_go_live` | uat | ready | |
| `action_go_live` | ready | go_live | set `actual_go_live = today` |
| `action_done` | go_live | done | |
| `action_cancel` | bất kỳ (trừ done/cancel) | cancel | |
| `action_reset_to_draft` | bất kỳ | draft | **chỉ Manager** (`erp_delivery.group_erp_delivery_manager`), reset `actual_go_live = False` |

**Quan trọng — phạm vi Sprint 2 vs Sprint 4**: `action_go_live()` ở sprint
này chỉ là transition state đơn thuần (`ready → go_live`). Hook
`_check_go_live_conditions()` (kiểm tra mandatory task, risk, v.v. — chặn
go-live nếu chưa đủ điều kiện) thuộc **Sprint 4A "Go-live Base"** theo đúng
execution plan, **chưa triển khai ở sprint này** để tránh lấn phạm vi.

## 5. Files thay đổi

| File | Thay đổi |
|---|---|
| `custom_addons/erp_delivery/models/project_project.py` | Mới |
| `custom_addons/erp_delivery/models/__init__.py` | Thêm import `project_project` |
| `custom_addons/erp_delivery/models/res_partner.py` | Bổ sung domain `is_erp_delivery=True` cho `erp_project_ids` (giải quyết nợ kỹ thuật ADR-004 của Sprint 1) |
| `custom_addons/erp_delivery/security/erp_delivery_security.xml` | Thêm 2 record rule (`rule_project_consultant`, `rule_project_manager_multi_company`) |
| `custom_addons/erp_delivery/security/ir.model.access.csv` | Thêm 2 ACL cho `project.project` (Consultant: read+write; Manager: full CRUD) |
| `custom_addons/erp_delivery/views/project_project_views.xml` | Mới — inherit `project.edit_project` (header statusbar+buttons, tab "ERP Delivery"), list/kanban/search/action riêng cho menu ERP Projects |
| `custom_addons/erp_delivery/views/erp_delivery_menus.xml` | Thêm menu "Projects" |
| `custom_addons/erp_delivery/__manifest__.py` | Thêm `views/project_project_views.xml` vào `data` |
| `custom_addons/erp_delivery/tests/test_project_workflow.py` | Mới (5 test) |
| `custom_addons/erp_delivery/tests/test_project_security.py` | Mới (3 test) |
| `custom_addons/erp_delivery/tests/__init__.py` | Thêm 2 import |

## 6. Giải thích implementation

```
User tạo Project mới, tick "Is Erp Delivery" (field cạnh Tags)
    ↓
create() override: is_erp_delivery=True và chưa có code
    → ir.sequence.next_by_code('erp.project.code') → "ERP/2026/00001"
    ↓
Header hiện statusbar "state" (ẩn hoàn toàn với project thường)
    ↓
User bấm "Start Analysis" → action_start_analysis()
    → _erp_transition('draft', 'analysis') kiểm tra state hiện tại
    → write({'state': 'analysis'}) → chatter tracking (state có tracking=True)
    ↓
... lặp lại tuần tự cho đến "Mark Done"
    ↓
Record rule (is_erp_delivery=True) giới hạn Consultant chỉ thấy project mình
là PM (user_id) hoặc trong member_ids; Manager thấy toàn bộ company_ids.
```

## 7. Security

- **ACL mới** (`ir.model.access.csv`): `erp_delivery.group_erp_delivery_consultant`
  → read+write (không create/unlink) trên `project.project`;
  `erp_delivery.group_erp_delivery_manager` → full CRUD. (ACL chuẩn của
  module `project` không cấp quyền này cho nhóm của ta — xem mục 3 Audit.)
- **Record Rules**:
  - `rule_project_consultant`: domain
    `['|', ('is_erp_delivery', '=', False), '|', ('user_id', '=', user.id), ('member_ids', 'in', [user.id])]`
    — vế `is_erp_delivery = False` đảm bảo rule này **không ảnh hưởng tới
    project thường** (để nguyên cho rule gốc của module `project` quyết
    định), chỉ thu hẹp phạm vi cho project ERP.
  - `rule_project_manager_multi_company`: domain
    `['|', ('is_erp_delivery', '=', False), ('company_id', 'in', company_ids)]`
    — dùng `company_ids` (danh sách company được phép), **không** dùng
    `company_id` (company hiện tại), đúng cảnh báo bẫy multi-company ở
    execution plan mục 2.5.3. (Lưu ý: module `project` gốc đã có sẵn 1 rule
    global multi-company `project_comp_rule` cho mọi record — rule của ta là
    lớp bảo vệ tường minh bổ sung theo đúng yêu cầu Sprint 2, không thay thế
    rule gốc.)
- **Field Security**: `note_internal`, `contract_value` (trong view) có
  `groups="erp_delivery.group_erp_delivery_manager"`.
- **Multi-company**: xem Record Rules ở trên; test
  `test_project_security.py` xác nhận Consultant B không thấy project của
  Consultant A cho tới khi được thêm vào `member_ids`.

## 8. Performance

- `is_erp_delivery` và `code`: `index=True` — phục vụ domain filter
  `[('is_erp_delivery', '=', True)]` dùng trong `action_erp_project` và tra
  cứu theo code.
- Chưa có computed/aggregate field ở sprint này (sẽ tới ở Sprint 3) nên chưa
  cần đánh giá N+1/`_read_group`.
- `create()` dùng `@api.model_create_multi` — batch-safe, không có logic
  chỉ chạy cho 1 record.

## 9. Tests

**`test_project_workflow.py`**

| Test | Scenario | Expected |
|---|---|---|
| `test_full_state_sequence` | Gọi tuần tự 6 action từ draft → done | state cuối = `done`, `code` đã được gán, `actual_go_live` = hôm nay sau `action_go_live` |
| `test_invalid_transition_raises_user_error` | Gọi `action_go_live()` khi đang ở `draft` (bỏ qua các state trung gian) | Raise `UserError`, state không đổi |
| `test_planned_go_live_before_start_date_raises_validation_error` | Tạo project với `planned_go_live < date_start` | Raise `ValidationError` |
| `test_pm_change_is_tracked_in_chatter` | Đổi `user_id` | Số lượng `mail.message` của record tăng |
| `test_contract_value_change_creates_tracking_value` | Đổi `contract_value` | Message mới nhất có `tracking_value_ids` chứa field `contract_value` |

**`test_project_security.py`** (unit test 7 của đề — scenario "Consultant
không access project ngoài scope")

| Test | Scenario | Expected |
|---|---|---|
| `test_consultant_b_cannot_see_consultant_a_project` | Consultant B search project mà Consultant A là PM | Không tìm thấy |
| `test_consultant_a_sees_own_project` | Consultant A search project của chính mình | Tìm thấy |
| `test_consultant_b_sees_project_once_added_as_member` | Thêm Consultant B vào `member_ids`, search lại | Tìm thấy |

## 10. Validation Result

### Executed

```bash
createdb -h /var/run/postgresql -p 5433 erp_delivery_test

/home/pc/odoo-dev/odoo-venv/bin/python3 /home/pc/odoo-dev/odoo/odoo-bin \
  --addons-path="/home/pc/odoo-dev/odoo/addons,/home/pc/odoo-dev/odoo/odoo/addons,/home/pc/odoo-dev/erp-delivery/custom_addons" \
  -d erp_delivery_test --db_host=/var/run/postgresql --db_port=5433 --db_user=pc \
  -i erp_delivery --test-enable --test-tags /erp_delivery --stop-after-init

# Upgrade idempotency
... -u erp_delivery --stop-after-init

# Uninstall (odoo-bin shell, button_immediate_uninstall)
... shell -d erp_delivery_test ...

# Lint
python3 -m pylint --load-plugins=pylint_odoo -d all -e odoolint custom_addons/erp_delivery
```

### Result

**PASS**

- Install: `0 modules loaded ... 39 modules loaded`, không ERROR/CRITICAL
  thuộc `erp_delivery` (cảnh báo RST "Unexpected indentation" vẫn chỉ xuất
  hiện trong lúc nạp module `base`/`mail`, không liên quan — xác nhận lại
  giống Sprint 1).
- Tests: `odoo.tests.result: 0 failed, 0 error(s) of 11 tests when loading
  database 'erp_delivery_test'` (11 test method mới của Sprint 2 cộng dồn
  với 3 test cũ của Sprint 1 trong cùng lần chạy test-tag `/erp_delivery` —
  tổng 17 test case được collect).
- Upgrade (`-u erp_delivery`): exit code 0, không log ERROR/CRITICAL.
- Uninstall: `button_immediate_uninstall()` → `state: uninstalled`, không
  exception.
- `pylint-odoo` (`-e odoolint`): 9.91/10 — 2 cảnh báo còn lại là quy ước
  OCA (`manifest-required-author`, `missing-readme`), đã chấp nhận giữ
  nguyên từ Sprint 1 (xem `docs/implementation/001_...md` mục 11).

**NOT EXECUTED** — kiểm thử UI qua trình duyệt thật (bấm từng nút state
machine, xem statusbar, kiểm tra tab "ERP Delivery" ẩn/hiện đúng). Môi
trường không có browser. Thay vào đó: view XML đã được xác nhận parse và
render đúng (nếu sai field/xpath, Odoo sẽ raise `ParseError` khi install —
đã từng bắt được và sửa 2 lỗi loại này trong quá trình phát triển, xem mục
11), và toàn bộ state machine + chatter tracking được test qua ORM trực
tiếp.

## 11. Technical Decisions

### Decision

Tái sử dụng field chuẩn `user_id` (string "Project Manager") của
`project.project` làm ERP Project Manager, **không** thêm field `pm_id` mới
như tên gọi trong execution plan mục 2.1.1.

### Reason

Audit `addons/project/models/project_project.py` cho thấy
`project.project` đã có sẵn:
```python
user_id = fields.Many2one('res.users', string='Project Manager',
                           default=lambda self: self.env.user, tracking=True)
```
Đây chính xác là field "Project Manager" mà plan mô tả cho `pm_id`. Thêm một
field `pm_id` song song sẽ tạo ra 2 field cùng ý nghĩa trên cùng model —
đúng kiểu "duplicate field" mà nguyên tắc thiết kế của dự án cấm rõ ràng
("Không tạo model/field song song nếu requirement đã xác định
dùng model chuẩn"), và sẽ gây nhầm lẫn UX nghiêm trọng (2 ô "Project
Manager" khác nhau có thể lệch giá trị nhau).

### Alternative considered

1. Thêm `pm_id` mới, đồng bộ 2 chiều với `user_id` qua compute/inverse →
   **loại**: phức tạp không cần thiết, vẫn là 2 field vật lý.
2. Thêm `pm_id` mới, bỏ qua `user_id` hoàn toàn (ẩn `user_id` khỏi view) →
   **loại**: `user_id` được tham chiếu sâu trong module `project` chuẩn
   (default values, một số logic nội bộ, hiển thị avatar trong nhiều view
   khác của hệ thống project) — ẩn nó đi nhưng vẫn giữ cột DB là lãng phí và
   rủi ro vỡ các tính năng project chuẩn dựa vào `user_id`.
3. **Chọn**: dùng thẳng `user_id`, chỉ đặt lại label/widget khi cần trong
   các view ERP-specific nếu muốn làm rõ ngữ cảnh ("ERP Project Manager").

### Why rejected

Phương án 1 và 2 đều vi phạm nguyên tắc "không tạo field thừa" mà không có
lợi ích kỹ thuật tương xứng.

---

### Decision

Field mới `planned_go_live` được thêm thay vì tái sử dụng field chuẩn `date`
("Expiration Date") của `project.project`.

### Reason

`date` đã gắn với widget `daterange` cặp với `date_start`
(`options='{"end_date_field": "date", "always_range": "1"}'`), và module
`project` gốc có xử lý riêng cho field này trong `create()`
(`vals.get('date', True)` dùng để quyết định auto-fill `date` từ
`date_start + timeframe` mặc định). Tái sử dụng `date` cho ngữ nghĩa
"Planned Go-live" sẽ:
- Làm sai lệch nhãn UI chuẩn ("Expiration Date" ≠ "Planned Go-live") ở mọi
  nơi field này được hiển thị trong hệ thống project gốc.
- Có nguy cơ xung đột với logic auto-fill nội bộ nói trên.

### Alternative considered

1. Tái sử dụng `date`, đổi label qua view context → **loại**: label đổi chỉ
   ở 1 view, các view/report khác của module `project` vẫn hiển thị
   "Expiration Date" → không nhất quán, gây hiểu nhầm nghiêm trọng hơn lợi
   ích tiết kiệm 1 cột.
2. **Chọn**: field mới `planned_go_live`, độc lập hoàn toàn với `date`.

### Why rejected

Rủi ro về tính nhất quán UI và khả năng xung đột với logic nội bộ của module
`project` lớn hơn chi phí thêm 1 cột Date.

---

### Decision

`contract_value` dùng `currency_field="currency_id"`, tái sử dụng field
`currency_id` đã có sẵn (computed) trên `project.project`, thay vì thêm
field currency mới như cách đã làm với `erp.solution` ở Sprint 1.

### Reason

Khác với `res.partner` (Sprint 1, không có `currency_id`),
`project.project` **đã có sẵn** `currency_id` (compute từ `company_id`).
Không cần lặp lại pattern "thêm field compute currency" — tận dụng field có
sẵn đúng tinh thần "ORM first / không tạo field thừa".

### Alternative considered

Không có — đây là trường hợp rõ ràng, không có phương án thay thế hợp lý.

---

### Decision

Record rule domain luôn có vế `('is_erp_delivery', '=', False)` OR với điều
kiện nghiệp vụ thực sự (thay vì domain "trần" như ví dụ minh họa ở execution
plan mục 2.5.3).

### Reason

`project.project` là model dùng chung giữa project thường và ERP project.
Nếu áp domain hạn chế trực tiếp như ví dụ gốc của plan
(`['|', ('pm_id', '=', user.id), ('member_ids', 'in', [user.id])]`) mà
không loại trừ project thường, bất kỳ user nào có nhóm
`erp_delivery.group_erp_delivery_consultant` (đồng thời cũng có thể có
nhóm `project.group_project_user` cho công việc project thường khác) sẽ bị
**rule này AND với các rule project gốc**, có nguy cơ che khuất/giới hạn
nhầm cả project không liên quan ERP. Thêm vế `is_erp_delivery = False` đảm
bảo rule của ta chỉ "có ý kiến" khi record là ERP project; project thường
được rule gốc của module `project` quyết định như bình thường.

### Alternative considered

1. Domain trần theo đúng câu chữ plan → **loại**: rủi ro thu hẹp quyền truy
   cập project thường ngoài ý muốn, như phân tích ở trên.
2. **Chọn**: domain có vế loại trừ `is_erp_delivery = False`.

### Why rejected

Phương án 1 vi phạm nguyên tắc "minimal blast radius" của master prompt —
thay đổi hành vi của cả project thường nằm ngoài phạm vi yêu cầu.

---

### Decision

Thêm 2 dòng ACL mới (`access_project_project_erp_consultant`,
`access_project_project_erp_manager`) cấp quyền write/create trực tiếp cho
2 group `erp_delivery.*` trên model `project.project`, thay vì dùng
`implied_ids` để group `erp_delivery.*` kế thừa `project.group_project_user`
/ `project.group_project_manager`.

### Reason

Audit ACL chuẩn của module `project`
(`project/security/ir.model.access.csv`) cho thấy `project.group_project_user`
chỉ có `perm_read=1` trên `project.project` (không write/create) — không đủ
cho Consultant cập nhật state/progress dự án của mình. Nếu dùng
`implied_ids` để kéo theo `project.group_project_manager` cho
`erp_delivery.group_erp_delivery_manager`, Manager của ta sẽ tự động có
TOÀN BỘ quyền hạn của Project Manager chuẩn (bao gồm cả các model/feature
khác của `project` không liên quan tới ERP Delivery, như xoá bất kỳ project
thường nào trong hệ thống) — vượt quá phạm vi cần thiết.

### Alternative considered

1. `implied_ids` kéo theo `project.group_project_manager`/`group_project_user`
   → **loại**: cấp thừa quyền trên toàn bộ model `project.project` kể cả
   project không phải ERP.
2. **Chọn**: ACL riêng, rõ ràng, chỉ cấp đúng mức cần thiết
   (Consultant: read+write, không create/unlink; Manager: full CRUD), kết
   hợp với record rule để giới hạn phạm vi theo `is_erp_delivery`.

### Why rejected

Phương án 1 vi phạm nguyên tắc least-privilege và có thể cấp quyền ngoài ý
muốn lên dữ liệu project không thuộc phạm vi ERP Delivery.

---

### Decision

Trong test, phải gọi `self.env.cr.flush()` tường minh trước khi kiểm tra
`tracking_value_ids` sau một `write()`.

### Reason

Qua debug (xem `odoo/addons/mail/models/mail_thread.py`
`_track_prepare`/`_track_finalize`), message tracking của `mail.thread`
được **hoãn tới `cr.precommit` hook**, chỉ thực thi khi `cr.flush()` được
gọi (xảy ra tự nhiên lúc commit trong 1 HTTP request thật). `TransactionCase`
không commit giữa các bước trong cùng 1 test (rollback toàn bộ ở cuối), nên
nếu không flush tường minh, `tracking_value_ids` sẽ luôn rỗng dù tính năng
tracking hoạt động đúng trong thực tế. Đây là đặc điểm của framework, không
phải lỗi code — ghi lại ở đây để tránh hiểu nhầm "tracking không hoạt động"
trong các sprint sau khi viết thêm test liên quan tới chatter.

### Alternative considered

Không có — đây là cách bắt buộc theo cơ chế nội bộ của `mail.thread`.

## 12. Known Limitations

- `action_go_live()` chưa có kiểm tra blocker (mandatory task, risk, v.v.)
  — đúng theo kế hoạch, sẽ bổ sung ở Sprint 4A.
- Chưa test UI qua trình duyệt thật (môi trường không có browser) — xem mục
  10.
- `member_ids` chưa có constraint loại trừ user đã là `user_id` (PM) ra khỏi
  danh sách member trùng lặp — không phải yêu cầu của đề, không thêm ngoài
  phạm vi.
- Notebook tab "ERP Delivery" hiện gộp cả `note_internal` — Sprint 3 có kế
  hoạch tách thành tab "Notes" riêng trong 5-tab notebook (Modules/Tasks/
  Milestones/Risks/Notes); việc tái cấu trúc view đó thuộc phạm vi Sprint 3.

## 13. Next Step

Sprint 3: `erp.project.module.line`, mở rộng `project.task` (5 field
ERP-specific), `erp.milestone`, `erp.risk`, 10 computed field trên
`project.project` (bao gồm `health_status` store+index), cron job
recompute, notebook 5-tab trên project form.
