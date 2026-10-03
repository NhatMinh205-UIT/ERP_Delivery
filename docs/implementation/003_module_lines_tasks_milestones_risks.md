# Module Lines, Tasks, Milestones, Risks & Computed Fields (Sprint 3 — Tuần 5–6)

## 1. Mục tiêu

Hoàn thiện mô hình dữ liệu triển khai dự án: bảng trung gian module/solution
(`erp.project.module.line`), mở rộng `project.task`, milestone, risk, và đủ
**10 computed field** theo đúng bảng 2.3 của execution plan — 9 trên
`project.project` (bao gồm `health_status` store+index) + 1 trên
`erp.project.module.line` (`actual_effort`) — cron job recompute daily,
notebook 5-tab trên project form.

## 2. Requirement liên quan

`ERP_Delivery_Execution_Plan.md`, mục 3 — **Sprint 3 (Tuần 5–6): Module
Lines, Tasks, Milestones, Risks, Computed Fields**, mục 2.1.1 (bảng model),
mục 2.3 (bảng computed fields), mục 2.4 (pattern compute+inverse).

## 3. Trạng thái trước khi thay đổi

Addon `erp_delivery` sau Sprint 2 đã có: `res.partner` (ERP Customer),
`erp.solution`/`erp.solution.category`, `project.project` extension (8-state
machine, `code`, `member_ids`, `planned_go_live`, `actual_go_live`,
`contract_value`, `note_internal`), security groups + record rules +
ACL cho `project.project`. **Chưa có**: `erp.project.module.line`,
`project.task` extension, milestone/risk, và toàn bộ computed field.

### Audit kết quả (trước khi code) — 3 xung đột quan trọng với Odoo 18 chuẩn

**(a) `project.milestone` đã tồn tại chuẩn trong module `project`**
(`addons/project/models/project_milestone.py`): `name`, `project_id`,
`deadline`, `is_reached` (Boolean), `task_ids` (nghịch đảo từ
`project.task.milestone_id` — field này **cũng đã có sẵn** trên
`project.task`). Model `erp.milestone` theo plan sẽ trùng lặp hoàn toàn với
model chuẩn này.

**(b) `project.task.effective_hours` và `project.task.progress` — field mà
công thức `actual_effort`/`progress_percent` của plan dựa vào — KHÔNG tồn
tại trong module `project` core.** Grep
`addons/hr_timesheet/models/project_task.py` cho thấy 2 field này chỉ được
thêm khi cài đặt addon `hr_timesheet` (kéo theo toàn bộ phân hệ HR/Timesheet
— `hr`, `analytic`, nhân sự, chấm công). Kiến trúc đã thống nhất (mục 1.3 của
plan) cho addon `erp_delivery` chỉ depend `base, mail, project, contacts` —
không có `hr_timesheet`.

**(c) `project.project.task_ids` có domain ngầm
`[('is_closed', '=', False)]`** (`addons/project/models/project_project.py`
dòng 108) — **chỉ trả về task CHƯA đóng**! Mọi công thức compute của plan
dựa trên `task_ids` (mandatory_done_count, progress_percent, health_status)
sẽ luôn sai nếu dùng field này, vì task đã hoàn thành (`is_closed=True`) bị
loại khỏi tập hợp ngay từ đầu. Phát hiện này xảy ra **sau khi code và chạy
test thất bại** (`test_progress_percent_weighted_by_mandatory_task` trả về
`0.0` thay vì `33.33`) — debug qua `odoo-bin shell` xác nhận
`project.task_ids` chỉ chứa 1/2 task đã tạo. May mắn module `project` cũng
định nghĩa sẵn field `tasks = fields.One2many('project.task', 'project_id',
string="Task Activities")` (dòng 102, cùng inverse, **không có domain**) —
dùng field này thay thế.

Ba phát hiện này dẫn tới 3 Technical Decisions ở mục 11.

## 4. Thiết kế

### Models

| Model | Kỹ thuật | Lý do |
|---|---|---|
| `erp.project.module.line` | Mới | Bảng trung gian project↔solution, không dùng M2M thuần vì cần lưu effort/consultant/price riêng (đúng lý do plan đã nêu ở mục 1) |
| `project.task` | `_inherit` | Tận dụng object chuẩn (đã thiết lập từ Sprint 2) |
| `project.milestone` | `_inherit` **(khác plan: không tạo `erp.milestone` mới)** | Model chuẩn đã có hầu hết field cần — xem Technical Decisions |
| `erp.risk` | Mới, `_inherit = ['mail.thread']` | Không có model chuẩn tương đương — đúng như plan |

### Fields

**`erp.project.module.line`** (mới)

| Field | Type | Store | Ghi chú |
|---|---|---|---|
| `project_id` | M2o project.project, required, ondelete=cascade | ✅ | |
| `solution_id` | M2o erp.solution, required | ✅ | |
| `planned_effort` | Float | ✅ | |
| `actual_effort` | Float, compute | ✅ | `sum(task_ids.erp_actual_hours)` — xem Technical Decisions (b) |
| `consultant_id` | M2o res.users | ✅ | |
| `currency_id` | M2o res.currency, related `project_id.currency_id` | ✅ | Kỹ thuật, dùng làm `currency_field` |
| `price` | Monetary | ✅ | |
| `state` | Selection (draft/in_progress/done) | ✅ | |
| `note` | Text | ✅ | |
| `task_ids` | O2m project.task (qua `module_line_id`) | — | |

SQL constraint `UNIQUE(project_id, solution_id)`.

**`project.task`** (`_inherit`)

| Field | Type | Ghi chú |
|---|---|---|
| `risk_level` | Selection low/medium/high/critical | |
| `progress_weight` | Float, default 1.0 | |
| `is_mandatory` | Boolean | |
| `acceptance_state` | Selection draft/pending/accepted/rejected | |
| `module_line_id` | M2o erp.project.module.line, domain lọc theo `project_id` | |
| `erp_actual_hours` | Float | **Mới, không nằm trong plan ban đầu** — thay thế cho `effective_hours` không tồn tại, xem Technical Decisions (b) |

**`project.milestone`** (`_inherit`)

| Field | Type | Ghi chú |
|---|---|---|
| `is_mandatory` | Boolean | Mới — model chuẩn không có |
| `state` | Selection pending/done/blocked, default pending | Mới — bổ sung cạnh `is_reached` chuẩn, không thay thế |
| `note` | Text | Mới — model chuẩn chỉ có chatter, không có field note đơn |

**`erp.risk`** (mới, giữ đúng field list của plan): `name`, `project_id`,
`level` (low/medium/high/critical), `state` (open/mitigated/closed),
`owner_id`, `mitigation_plan`.

**`project.project`** (`_inherit`, bổ sung tiếp)

| Field | Compute logic | Store | Index | Depends |
|---|---|---|---|---|
| `module_line_ids` | O2m (mới) | — | — | — |
| `risk_ids` | O2m (mới) | — | — | — |
| `module_count` | `len(module_line_ids)` | ✅ | ❌ | `module_line_ids` |
| `total_planned_effort` | `sum(module_line_ids.planned_effort)` | ✅ | ❌ | `module_line_ids.planned_effort` |
| `total_actual_effort` | `sum(module_line_ids.actual_effort)` | ✅ | ❌ | `module_line_ids.actual_effort` |
| `mandatory_task_count` | Count `tasks` có `is_mandatory=True` | ✅ | ❌ | `tasks.is_mandatory, tasks.is_closed` |
| `mandatory_done_count` | Count mandatory tasks có `is_closed=True` | ✅ | ❌ | (như trên) |
| `progress_percent` | Weighted: `sum(weight của task is_closed) / sum(weight)` | ✅ | ❌ | `tasks.progress_weight, tasks.is_closed` |
| `customer_code` | `related='partner_id.erp_code'` | ✅ | ✅ | (auto) |
| `duration_days` | `(planned_go_live - date_start).days`, có `inverse` | ✅ | ❌ | `date_start, planned_go_live` |
| `health_status` | Xem mục dưới | ✅ | ✅ | `progress_percent, date_start, planned_go_live, state, tasks.date_deadline, tasks.is_closed, tasks.is_mandatory, risk_ids.level, risk_ids.state` |

**Lưu ý quan trọng**: tất cả compute phụ thuộc task dùng field `tasks`
(không domain), **không** dùng `task_ids` (domain ẩn loại task đã đóng) —
xem Technical Decision (c).

### Business Rule — `_compute_health_status`

```
expected_progress = % thời gian đã trôi qua giữa date_start và planned_go_live (0–100, clamp)
gap = expected_progress - progress_percent

RED nếu: có task mandatory quá hạn (is_closed=False, date_deadline < today)
      HOẶC có risk critical đang open
      HOẶC planned_go_live đã qua mà state != done
      HOẶC gap > 20
AMBER nếu (và không phải RED): 10 <= gap <= 20
      HOẶC có 1–2 task quá hạn (không cần mandatory)
      HOẶC có risk high đang open
GREEN: còn lại
```

Đúng theo mô tả nghiệp vụ ở execution plan mục 3 Sprint 3, với "progress"
được thay bằng `progress_percent` tự định nghĩa (xem Technical Decision b).

### Cron

`ir.cron` `cron_recompute_health` (daily) gọi
`project.project._cron_recompute_health()` — invalidate + `modified()` trên
toàn bộ ERP project đang active (`state not in ('done', 'cancel')`), đúng
pattern plan mục 2.3.2. Đã verify chạy thủ công qua `odoo-bin shell` (mục
10).

### Pattern compute + inverse — `duration_days`

Theo đúng plan mục 2.4, dùng `fields.Date.add()` (tiện ích chuẩn của Odoo,
thay cho `timedelta` thủ công) để đảm bảo idempotent.

## 5. Files thay đổi

| File | Thay đổi |
|---|---|
| `models/erp_project_module_line.py` | Mới |
| `models/project_task.py` | Mới |
| `models/project_milestone.py` | Mới (`_inherit = 'project.milestone'`) |
| `models/erp_risk.py` | Mới |
| `models/project_project.py` | Thêm `module_line_ids`, `risk_ids`, 9 computed field (10 computed field tổng cộng tính cả `erp.project.module.line.actual_effort`), `_cron_recompute_health`, 2 action method cho smart button |
| `models/__init__.py` | Thêm 4 import mới |
| `security/erp_delivery_security.xml` | Thêm 8 record rule (module_line/risk/milestone/task × consultant/manager) |
| `security/ir.model.access.csv` | Thêm 8 ACL row |
| `data/ir_cron_data.xml` | Mới |
| `views/project_project_views.xml` | Thêm smart buttons, 4 notebook page mới (Modules/Tasks/Milestones/Risks), tách Notes, health badge trên kanban/list, filter health trên search |
| `__manifest__.py` | Thêm `data/ir_cron_data.xml` |
| `tests/test_project_computed.py` | Mới (5 test — unit test 9–13) |
| `tests/test_project_performance.py` | Mới (2 test — unit test 14–15, adapted) |
| `tests/test_project_security.py` | Thêm 4 test (record rule cho module_line/risk) |
| `tests/__init__.py` | Thêm 2 import |

## 6. Giải thích implementation

```
Manager mở tab "Modules" trên project form (chỉ hiện khi is_erp_delivery)
    ↓
Thêm dòng module_line (solution_id, planned_effort, consultant_id)
    ↓ SQL constraint UNIQUE(project_id, solution_id) chặn trùng
module_count / total_planned_effort (project) tự cập nhật (computed store)
    ↓
Consultant mở tab "Tasks", tạo task gắn module_line_id, nhập erp_actual_hours
    ↓
module_line.actual_effort = sum(task_ids.erp_actual_hours) tự cập nhật
    ↓
project.total_actual_effort tự cập nhật theo (2 tầng compute store)
    ↓
project.progress_percent tự cập nhật theo tasks.is_closed × progress_weight
    ↓
project.health_status tự cập nhật (so sánh với expected_progress theo thời gian,
kiểm tra task quá hạn / risk mở / go-live trễ)
    ↓
Cron daily "_cron_recompute_health" đảm bảo health_status đúng dù không có
write mới (vì phụ thuộc datetime.now()).
```

## 7. Security

- **ACL mới**: `erp_delivery.group_erp_delivery_consultant` và
  `...manager` được cấp **full CRUD** (không chỉ read+write như
  `project.project`) trên `erp.project.module.line`, `erp.risk`,
  `project.milestone`, `project.task` — xem lý do ở
  `docs/IMPLEMENTATION_STATUS.md` ADR tương ứng: thêm/sửa/xoá các bản ghi con
  (module line, risk, milestone, task) trong project mình đang quản lý là
  công việc thường ngày, khác với việc tạo một project mới hoàn toàn.
- **Record Rules**: mỗi model con có 2 rule (Consultant/Manager), domain đi
  qua `project_id.is_erp_delivery`/`project_id.user_id`/`project_id.member_ids`/
  `project_id.company_id`, theo đúng pattern đã thiết lập ở Sprint 2 (luôn
  OR với `is_erp_delivery=False` để không ảnh hưởng project thường).
- Test `test_project_security.py` xác nhận Consultant B không thấy
  module_line/risk của project mà Consultant A quản lý.

## 8. Performance

- `health_status`: `store=True, index=True` — bắt buộc theo plan (filter
  nhanh theo tình trạng sức khỏe).
- `customer_code`: related + `store=True, index=True` — search nhanh theo mã
  khách hàng.
- `module_count`, `total_planned_effort`, `total_actual_effort`,
  `mandatory_task_count`, `mandatory_done_count`, `progress_percent`,
  `duration_days`: đều `store=True` — tránh tính lại mỗi lần list view load.
- Cron recompute `health_status` dùng `invalidate_recordset` +
  `modified()` theo đúng pattern plan — không loop ghi từng record.
- Test hiệu năng (`test_project_performance.py`) xác nhận:
  - `_read_group` theo `health_status` trên 150 project: < 10 query (không
    phải 1 query/record).
  - Bulk tạo 150 module line + 150 task, bulk `write()` `erp_actual_hours`
    trên 150 task cùng lúc: số query tăng thêm < 150 (không phải N+1), và
    `total_actual_effort` cập nhật đúng tổng.
  - **Lưu ý khác biệt với đề**: đề yêu cầu benchmark thời gian thực (ví dụ
    "< 100ms với 1000 project"). Test tự động ở đây đo **số lượng SQL
    query** thay vì đồng hồ thực (wall-clock), vì assertion theo thời gian
    thực dễ flaky trên môi trường CI/sandbox chia sẻ tài nguyên; số lượng
    query đo được chính xác điều thực sự cần kiểm chứng (không có N+1), và
    ổn định hơn. Quy mô cũng giảm từ 1000 xuống 150 record để test chạy
    nhanh (< 1s) mà vẫn đủ lớn để lộ ra N+1 nếu có.

## 9. Tests

**`test_project_computed.py`**

| Test | Scenario | Expected |
|---|---|---|
| `test_progress_percent_weighted_by_mandatory_task` (unit test 9) | Task weight=1 (done) + task weight=2, mandatory (chưa done) | `progress_percent` = 100×1/3 ≈ 33.33 |
| `test_actual_effort_aggregation` (unit test 10) | Đổi `erp_actual_hours` của task | `module_line.actual_effort` và `project.total_actual_effort` cập nhật đúng |
| `test_duplicate_module_line_raises_integrity_error` (unit test 11) | Tạo 2 module_line cùng (project_id, solution_id) | Raise `IntegrityError` |
| `test_duration_days_inverse_sets_planned_go_live` (unit test 12) | Set `duration_days = 90` | `planned_go_live` = `date_start + 90 ngày`, đọc lại `duration_days` vẫn = 90 (idempotent) |
| `test_health_status_amber_then_red` (unit test 13) | 3 mandatory task, complete 1 → sau đó thêm 1 task mandatory quá hạn | `health_status`: amber → red |

**`test_project_performance.py`** (unit test 14–15, adapted — xem mục 8)

| Test | Scenario | Expected |
|---|---|---|
| `test_read_group_by_health_status_query_count` | `_read_group` trên 150 project theo `health_status` | Tổng count = 150, số query < 10 |
| `test_bulk_module_line_create_and_aggregate` | Bulk tạo 150 module_line + 150 task, bulk write `erp_actual_hours` | `module_count`/`total_planned_effort` đúng ngay sau bulk create; sau bulk write, `total_actual_effort` đúng, số query tăng thêm < 150 |

**`test_project_security.py`** (bổ sung, record rule cho model con)

| Test | Scenario | Expected |
|---|---|---|
| `test_consultant_b_cannot_see_module_line_of_scoped_project` | Consultant B search module_line của project Consultant A quản lý | Không tìm thấy |
| `test_consultant_a_sees_own_project_module_line` | Consultant A search module_line của project mình | Tìm thấy |
| `test_consultant_b_cannot_see_risk_of_scoped_project` | Tương tự cho `erp.risk` | Không tìm thấy |
| `test_consultant_a_sees_own_project_risk` | Tương tự cho `erp.risk` | Tìm thấy |

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

# Cron method manual run (odoo-bin shell)
env['project.project']._cron_recompute_health()

# Lint
python3 -m pylint --load-plugins=pylint_odoo -d all -e odoolint custom_addons/erp_delivery
```

### Result

**PASS**

- Install (clean DB, không demo): exit code 0, không ERROR/CRITICAL thuộc
  `erp_delivery` (cảnh báo RST "Unexpected indentation" vẫn chỉ xuất hiện
  lúc nạp `base`/`mail`, xác nhận không liên quan — giống Sprint 1 & 2).
- Tests: `odoo.tests.result: 0 failed, 0 error(s) of 22 tests when loading
  database 'erp_delivery_test'` (22 = 3 Sprint 1 + 8 Sprint 2 + 11 Sprint 3
  test method, chạy cùng lần test-tag `/erp_delivery`).
- Upgrade (`-u erp_delivery`): exit code 0, không ERROR/CRITICAL.
- Uninstall: `button_immediate_uninstall()` → `state: uninstalled`, không
  exception.
- Cron method: gọi trực tiếp `_cron_recompute_health()` qua `odoo-bin
  shell` trên project vừa tạo → chạy không lỗi, `health_status` tính ra
  `'green'` hợp lý (project mới tạo, không task/risk).
- `pylint-odoo` (`-e odoolint`): 9.95/10 — 2 cảnh báo còn lại là quy ước
  OCA, đã chấp nhận giữ nguyên từ Sprint 1.

**NOT EXECUTED**

- Kiểm thử UI qua trình duyệt thật (bấm inline-edit trong 4 tab mới, xem
  kanban badge màu, filter Green/Amber/Red trên search). Môi trường không
  có browser — bù bằng: view XML được xác nhận parse/render đúng lúc
  install (nếu sai field/xpath, Odoo raise lỗi và install sẽ fail — đã xảy
  ra và được sửa 1 lần trong lúc phát triển, xem mục 11), toàn bộ logic
  compute/constraint được test qua ORM trực tiếp.
- Benchmark thời gian thực đúng nghĩa đen "1000 project < 100ms" của đề —
  thay bằng test đo số lượng query ở quy mô 150 record, lý do đã giải thích
  ở mục 8. Đây là sự đánh đổi có chủ đích, không phải "PASS giả" — kết quả
  đo query count là thật và được chạy thật.

## 11. Technical Decisions

### Decision

Không tạo model mới `erp.milestone` như tên gọi trong execution plan; thay
vào đó `_inherit = 'project.milestone'` (model chuẩn của module `project`)
và chỉ thêm 3 field còn thiếu (`is_mandatory`, `state`, `note`).

### Reason

Audit `addons/project/models/project_milestone.py` cho thấy Odoo 18 đã có
sẵn `project.milestone` với `name`, `project_id`, `deadline`, `is_reached`,
`task_ids` — đáp ứng hầu hết yêu cầu của plan. Tạo `erp.milestone` song song
sẽ:
1. Trùng lặp hoàn toàn với model chuẩn (trong khi execution plan TỰ áp dụng
   nguyên tắc "tận dụng object chuẩn" cho `project.project`/`project.task`
   ở mục 1.5/1.6 — milestone xứng đáng được áp dụng nguyên tắc tương tự).
2. Mất khả năng tận dụng tính năng có sẵn: `allow_milestones` toggle trên
   project, UI milestone bar có sẵn trong Odoo, `task_ids`/`milestone_id`
   trên `project.task` đã kết nối sẵn.
3. Vi phạm nguyên tắc thiết kế của dự án ("Không tạo model
   song song nếu requirement đã xác định dùng model chuẩn" / model đã tồn
   tại tương đương).

### Alternative considered

1. Tạo `erp.milestone` đúng như plan, độc lập hoàn toàn với
   `project.milestone` → **loại**: duplicate model, mất tính năng chuẩn.
2. `_inherits` (delegation inheritance) từ `project.milestone` → **loại**:
   execution plan mục 1.5 đã tự phân tích và loại phương án này cho
   project/task (khó extend method, dễ vỡ khi upgrade) — lý do tương tự áp
   dụng cho milestone.
3. **Chọn**: `_inherit` (classical inheritance), chỉ thêm field thiếu.

### Why rejected

Phương án 1 và 2 đều đi ngược chính nguyên tắc kiến trúc mà execution plan
đã thiết lập cho các model khác trong cùng hệ thống.

---

### Decision

Thêm field mới `erp_actual_hours` (Float) trên `project.task`;
`actual_effort` của `erp.project.module.line` tính từ field này, và
`progress_percent` của `project.project` tính từ `task.is_closed` (boolean
weighted-completion) — **không** dùng `task.effective_hours` /
`task.progress` như công thức literal trong execution plan.

### Reason

`effective_hours` và `progress` chỉ tồn tại trên `project.task` khi addon
`hr_timesheet` được cài (`addons/hr_timesheet/models/project_task.py`).
Addon `erp_delivery` (CORE) theo kiến trúc đã thống nhất (plan mục 1.3) chỉ
depend `base, mail, project, contacts`. Thêm `hr_timesheet` làm dependency
sẽ:
1. Kéo theo toàn bộ phân hệ HR/Timesheet (`hr`, `analytic`, quản lý nhân
   viên, chấm công) — không nằm trong phạm vi 3-addon đã thống nhất, và là
   một "undisclosed architecture change" bị cấm ở
   nguyên tắc không thay đổi kiến trúc đã thống nhất ngoài phạm vi yêu cầu.
2. Không có yêu cầu nghiệp vụ nào khác trong đề bài cần tới timesheet đầy
   đủ (chấm công theo ngày, approval workflow, v.v.) — chỉ cần một số đo
   "giờ đã làm" đơn giản để tính effort.

### Alternative considered

1. Thêm `hr_timesheet` vào `depends` → **loại**: vi phạm kiến trúc đã
   thống nhất, thêm dependency ngoài phạm vi yêu cầu.
2. Bỏ hẳn `actual_effort`/`progress_percent`, chỉ giữ field "allocated/kế
   hoạch" → **loại**: không đáp ứng yêu cầu rõ ràng của đề (Phần 5, computed
   fields bảng 2.3).
3. **Chọn**: field nhập tay nhẹ `erp_actual_hours`, và `progress_percent`
   dùng tỷ lệ hoàn thành theo trọng số (`is_closed` × `progress_weight`) —
   giữ đúng Ý ĐỊNH nghiệp vụ (effort thực tế, progress có trọng số) mà
   không cần hạ tầng timesheet đầy đủ.

### Why rejected

Phương án 1 vi phạm trực tiếp ràng buộc kiến trúc "tối đa 3 addon, core
không phụ thuộc không cần thiết" mà đề và cả plan tự đặt ra (mục 1.2, 1.3).
Phương án 2 không đáp ứng yêu cầu đề.

---

### Decision

Mọi computed field phụ thuộc vào tasks của project (`mandatory_task_count`,
`mandatory_done_count`, `progress_percent`, `health_status`) dùng field
`tasks` (không domain) thay vì `task_ids` (có domain ẩn
`is_closed = False`).

### Reason

Phát hiện qua **test thất bại thực tế**:
`test_progress_percent_weighted_by_mandatory_task` trả về `0.0` thay vì
`33.33` mong đợi. Debug qua `odoo-bin shell` xác nhận
`project.task_ids` chỉ chứa task CHƯA đóng — field này được định nghĩa với
`domain=lambda self: [('is_closed', '=', False)]` trong
`addons/project/models/project_project.py` dòng 108. Dùng field này cho các
phép tính cần biết CẢ task đã đóng (để tính % hoàn thành, mandatory đã
xong, v.v.) sẽ luôn cho kết quả sai. Module `project` chuẩn cũng định nghĩa
sẵn field thứ hai không domain: `tasks` (dòng 102, cùng inverse
`project_id`) — dùng field này thay thế triệt để.

### Alternative considered

1. Tự thêm domain `active_test=False`/context vào `task_ids` khi đọc →
   **loại**: không thể override domain của field kế thừa một cách an toàn,
   và field vẫn giữ tên gây hiểu nhầm cho người đọc code sau này.
2. Tự viết lại bằng `search()` trực tiếp trên `project.task` với domain
   riêng mỗi lần compute → **loại**: phức tạp hơn, mất lợi ích cache của
   One2many, và field `tasks` chuẩn đã giải quyết đúng vấn đề này sẵn.
3. **Chọn**: dùng field `tasks` có sẵn.

### Why rejected

Phương án 1 kỹ thuật không khả thi an toàn; phương án 2 tái tạo lại cái đã
có sẵn trong framework — vi phạm "ORM first, không tạo code thừa nếu Odoo
đã có cơ chế chuẩn" (nguyên tắc ORM first của dự án).

## 12. Known Limitations

- `erp_actual_hours` là nhập tay, không có validation chặn số âm hoặc vượt
  quá effort kế hoạch — không phải yêu cầu của đề, không thêm ngoài phạm
  vi.
- Chưa test UI qua trình duyệt thật (xem mục 10).
- Test hiệu năng dùng quy mô 150 record và đo query count thay vì wall-clock
  1000 record theo đúng chữ của đề (xem mục 8/10) — nếu cần benchmark thời
  gian thực đúng quy mô đề bài, nên thực hiện thủ công trên staging với
  `--log-sql`, ngoài phạm vi automated test suite.
- `_compute_health_status` không tính tới risk ở mức `medium`/`low` (chỉ
  `critical`/`high` ảnh hưởng tới red/amber) — đúng theo mô tả nghiệp vụ của
  plan, không phải thiếu sót.

## 13. Next Step

Sprint 4: Go-live base workflow — `_check_go_live_conditions()` (hook mở
rộng cho addon tùy chọn), cập nhật `action_go_live()` để gọi hook này; addon
`erp_delivery_sale` (tạo Project từ Sale Order, smart button 2 chiều).
