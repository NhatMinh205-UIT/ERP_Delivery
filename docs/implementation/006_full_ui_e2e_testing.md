# Full UI / E2E Testing with Playwright (Post-Sprint 5)

## 1. Mục tiêu

Dùng Playwright điều khiển trình duyệt thật (Chromium headless) thao tác
trên Odoo 18 thật (không phải ORM/TransactionCase) để kiểm thử toàn bộ hệ
thống ERP Delivery (`erp_delivery`, `erp_delivery_sale`,
`erp_delivery_quality`) qua giao diện: Customer, Solution, Project, Module,
Task, Milestone, Risk, Sales Integration, Go-live, Quality Gate — happy
path, validation/error, permission theo role, multi-company, và các
blocker. Audit test case backend hiện có và chuyển các scenario phù hợp
sang UI/E2E.

**Nguyên tắc tuân thủ nghiêm ngặt theo yêu cầu**: không sửa code trước khi
xác định rõ lỗi; không đánh dấu PASS nếu chưa thực sự thao tác qua UI; mọi
lỗi phát hiện đều ghi rõ bước tái hiện, expected, actual, nguyên nhân, file
liên quan, kèm screenshot.

## 2. Môi trường thiết lập

- Cài Playwright (Python) + Chromium headless vào venv hiện có
  (`odoo-venv/bin/pip install playwright`, `python3 -m playwright install
  chromium` — không có quyền `sudo` cho `--with-deps` nên chỉ tải browser
  binary; verify binary tự chạy được không cần thêm system lib).
- Chạy Odoo **thật** (HTTP server, không phải `--stop-after-init`) trên DB
  `erp_ui_test`, cài cả 3 addon (`erp_delivery,erp_delivery_sale,
  erp_delivery_quality`), port 8169.
- Fixture tối thiểu tạo qua shell (KHÔNG phải nghiệp vụ đang test, chỉ là
  thiết lập tài khoản — tương đương việc admin tạo user mới qua Settings >
  Users trong đời thực): mật khẩu admin, 1 company phụ ("Company B (UI
  Test)"), 2 user test (`ui_consultant` nhóm Consultant, `ui_manager` nhóm
  Manager, scoped vào Company B).
- Toàn bộ **nghiệp vụ** (tạo customer, solution, project, module, task,
  milestone, risk, sale order, quality assessment, chuyển state, Go-live)
  đều thao tác qua browser thật — không bypass qua ORM, trừ 1 workaround
  được ghi rõ ở Finding #3 (set `partner_id` qua shell vì field bị ẩn khỏi
  UI, chỉ để tiếp tục kiểm thử phần còn lại của workflow).

## 3. Audit test case backend → chuyển sang UI/E2E

| Backend test (Sprint 1–5) | Chuyển thành UI scenario | Trạng thái |
|---|---|---|
| `test_erp_code_duplicate_raises_integrity_error` | S01-03: tạo 2 contact ERP trùng `erp_code` qua form | Chạy — phát hiện **Finding #1** (khác kết quả backend) |
| `test_consultant_cannot_read_internal_cost` | S03-05/06/07: Consultant mở Solution form | PASS — khớp backend |
| `test_full_state_sequence`, `test_go_live` | S04/S07: đi hết state machine qua statusbar, Go-Live | PASS — khớp backend, thêm bằng chứng cooperative inheritance qua dialog thật |
| `test_project_security.py` (scenario #1) | S09 (mở rộng): Consultant/Manager scoped search | Chạy — phát hiện **Finding #4 (CRITICAL)**, khác hẳn kết quả backend |
| `test_multicompany.py` (scenario #2) | S09: Manager company B xem list Project | Chạy — cùng root cause Finding #4 |
| `test_sales_integration.py` (scenario #5) | S08: SO → Create ERP Project → smart button 2 chiều | PASS — khớp backend, thêm Finding #2 (field ẩn) |
| `test_quality_gate.py` + `test_cooperative.py` (scenario #6, #7) | S04/S07: dialog Go-Live liệt kê cả Quality + base blockers cùng lúc | PASS — bằng chứng trực quan cooperative inheritance |
| `test_project_computed.py` (scenario #3, aggregate) | S05/S07: smart button Modules/Tasks/Mandatory Tasks tự cập nhật số liệu sau khi thêm dữ liệu qua UI | PASS (quan sát qua số liệu smart button thay đổi 0→1, 0/0→1/1) |

Không chuyển sang UI: `test_project_performance.py` (đo query count — không
có ý nghĩa đo qua UI/browser), `test_go_live.py` các test blocker riêng lẻ
chi tiết (đã có 1 scenario tổng hợp đại diện qua UI, test riêng từng điều
kiện qua UI sẽ trùng lặp không cần thiết với test backend đã PASS).

## 4. Kết quả tổng hợp

| Trạng thái | Số lượng |
|---|---|
| **PASS** (xác nhận qua thao tác UI thật) | 24 |
| **FAIL / Finding** (lỗi thật, xem mục 5) | 6 điểm (gộp thành 5 Finding, 1 trong đó Critical) |
| **INFO** (quan sát, không phải pass/fail nhị phân) | 4 |
| **BLOCKED** | 0 (không có scenario nào hoàn toàn không thể thao tác) |
| **NOT EXECUTED** | xem mục 7 |

Chi tiết từng bước + kết quả nằm trong các file JSON log tại thời điểm chạy
(`results_s0*.json`, lưu tạm trong scratchpad phiên làm việc — không phải
phần repository lâu dài; bằng chứng lâu dài là 14 screenshot đã lưu tại
`docs/implementation/screenshots/006_ui_e2e/`).

## 5. Findings (lỗi thật phát hiện qua UI, chưa sửa)

### 🔴 Finding #1 (CRITICAL) — Record rules không có hiệu lực thật với user nội bộ thông thường

**Bước tái hiện:**
1. Tạo user `ui_consultant`: chỉ có nhóm `erp_delivery.group_erp_delivery_consultant` + `base.group_user` (bắt buộc để login — xem Finding setup note bên dưới).
2. User này KHÔNG phải PM, KHÔNG phải `member_ids` của bất kỳ project ERP nào.
3. `env['project.project'].with_user(ui_consultant).search([('is_erp_delivery','=',True)])`

**Expected:** 0 project (theo ADR-008, record rule `rule_project_consultant`: chỉ thấy project mình là PM hoặc member).

**Actual:** Trả về **TẤT CẢ** project ERP trong hệ thống (2/2), bất kể không liên quan gì tới user đó. Tương tự, Manager B (chỉ thuộc Company B) nhìn thấy project của Company A qua UI (screenshot `14_FINDING_multicompany_record_rule_leak.png`).

**Nguyên nhân:** Đọc `odoo/addons/base/models/ir_rule.py` method `_compute_domain()` (dòng 142–169): Odoo gom **TẤT CẢ** rule mà user match (bất kể rule đó thuộc group/module nào) vào một `group_domains` list duy nhất, rồi **OR** toàn bộ lại, sau đó mới AND với global rules. `erp_delivery` định nghĩa `rule_project_consultant`/`rule_project_manager_multi_company` cho nhóm Consultant/Manager — nhưng module `project` CHUẨN (core) đã có sẵn rule `project_public_members_rule` ("Project: employees: following required for follower-only projects") gắn với nhóm `base.group_user` (Internal User), với domain gần như LUÔN ĐÚNG (`privacy_visibility != 'followers'`, mặc định `privacy_visibility='portal'`). Vì **mọi** nhân viên nội bộ thật sự (không phải user test thiếu `base.group_user`) đều có nhóm `base.group_user`, rule permissive này LUÔN được OR vào, và vì chỉ cần 1 rule trong OR đúng là cả nhóm domain đúng → **toàn bộ hạn chế của `erp_delivery` bị vô hiệu hoá** cho bất kỳ user nội bộ thật nào.

**Vì sao 31+ test backend đã PASS không phát hiện ra:** `test_project_security.py` (Sprint 2) và `test_multicompany.py` (Sprint 5) tạo user test KHÔNG gán `base.group_user` (chỉ gán `erp_delivery.group_erp_delivery_consultant`/`manager`). User "thiếu" `base.group_user` không match rule `project_public_members_rule` của core, nên domain đó không được OR vào — **kết quả test backend PASS theo đúng Technical Decision thiết kế, nhưng không phản ánh user thật** (mọi user nội bộ thật BẮT BUỘC có `base.group_user`, xác nhận lại qua chính lỗi "Forbidden...User types/Internal User" gặp phải lúc đầu khi test UI — xem mục 6).

**File liên quan:**
- `custom_addons/erp_delivery/security/erp_delivery_security.xml` (toàn bộ 8 record rule theo pattern `is_erp_delivery=False OR ...` — ADR-008 — rất có thể TẤT CẢ đều bị ảnh hưởng tương tự: `rule_project_consultant`, `rule_project_manager_multi_company`, `rule_module_line_*`, `rule_risk_*`, `rule_milestone_*`, `rule_task_*`)
- `custom_addons/erp_delivery_quality/security/erp_delivery_quality_security.xml` (2 rule `rule_quality_assessment_*`, cùng pattern)
- `custom_addons/erp_delivery/tests/test_project_security.py`, `test_multicompany.py` (test fixture không đại diện user thật)
- Root cause framework: `odoo/addons/base/models/ir_rule.py::_compute_domain` (hành vi chuẩn của Odoo, không phải bug framework — là hệ quả thiết kế của ADR-008 không tương thích với cơ chế OR-toàn-cục của Odoo)

**Mức độ ảnh hưởng:** Nghiêm trọng — vô hiệu hoá scenario #1 và #2 của đề (2 trong 8 scenario bắt buộc) cho user thật. Field-level group (`internal_cost` trên `erp.solution`) KHÔNG bị ảnh hưởng (cơ chế khác — ACL field-level, không qua `ir.rule`, xem Finding #3' note).

**Khuyến nghị (không tự sửa theo yêu cầu):** cần thiết kế lại domain record rule để không dựa vào escape-hatch `is_erp_delivery=False OR ...` kết hợp với kỳ vọng "chỉ rule của mình match". Hướng khả thi: đổi `_compute_domain` behavior không khả thi (framework), nên cần tự đảm bảo domain của chính rule mình chặt chẽ mà không phụ thuộc giả định "không rule nào khác được OR vào" — ví dụ domain phải tự chứa đủ điều kiện (`is_erp_delivery=False OR (is_erp_delivery=True AND (user_id=... OR member_ids...))`) nhưng vấn đề KHÔNG nằm ở domain của chính ta (đã đúng), mà ở việc rule KHÁC từ module project được OR cùng nhóm — đây là giới hạn kiến trúc của ir.rule, cần nghiên cứu kỹ hướng xử lý (có thể cần field `privacy_visibility='followers'` mặc định cho project ERP để vô hiệu hoá nhánh permissive của rule lõi, nhưng cần đánh giá tác dụng phụ kỹ trước khi áp dụng).

---

### 🟠 Finding #2 (HIGH) — Trường Customer (partner_id) biến mất hoàn toàn khỏi form Project ERP khi cài `erp_delivery_sale`

**Bước tái hiện:**
1. Cài `erp_delivery` + `erp_delivery_sale` (hoặc cả 3 addon).
2. ERP Delivery → Projects → New.
3. Quan sát form: không có field "Customer" ở đâu cả (`page.locator("text=Customer").count()` = 0, `[name=partner_id]` = 0 phần tử).

**Expected:** Field Customer hiển thị bình thường như mọi field khác (plan yêu cầu partner_id là field cốt lõi, dùng trong `_check_go_live_conditions`, `customer_code` related, v.v.)

**Actual:** Field hoàn toàn không render — kể cả khi `partner_id` đã được set qua ORM, UI vẫn không hiển thị nó ở bất kỳ đâu trên form chính.

**Nguyên nhân:** Addon chuẩn Odoo `sale_project` (auto-install khi `sale_management`+`project_account` cùng có mặt — **xác nhận xảy ra thật** trong DB test: `sale`→`account_payment`→`account`, kết hợp `project`→`project_account`→auto-install `sale_project`) có view kế thừa riêng (`project.project.view.inherit`, id riêng, sibling với view của ta) redefine `partner_id`:
```xml
<field name="partner_id" ... invisible="not allow_billable" .../>
```
`allow_billable` là field của `sale_project`, mặc định `False`, và `erp_delivery`/`erp_delivery_sale` không bao giờ set nó `True`. Khi nhiều view cùng inherit 1 field, Odoo gộp TẤT CẢ thuộc tính lại — `invisible` từ `sale_project` áp dụng bất kể project có phải ERP hay không.

**File liên quan:**
- Không phải lỗi trong code của ta — xung đột giữa addon chuẩn `sale_project` (file `addons/sale_project/views/project_views.xml` trong Odoo core) và field `partner_id` dùng chung.
- Ảnh hưởng: `custom_addons/erp_delivery_sale/` (addon của ta kéo theo `sale_project` một cách gián tiếp, không khai báo trực tiếp).

**Mức độ ảnh hưởng:** Cao — PM không thể set/sửa Customer qua UI chính của project khi đã cài Sales Integration (phải tạo project từ Sale Order để field này được set tự động qua code, hoặc phải tìm cách khác). Không ảnh hưởng khi CHỈ cài `erp_delivery` (không có `sale_project`).

**Khuyến nghị:** Thêm 1 view override trong `erp_delivery_sale` (hoặc `erp_delivery`) ghi đè lại `invisible` của `partner_id` thành `invisible="False"` (hoặc điều kiện phù hợp) khi `is_erp_delivery=True`, để đảm bảo field luôn hiển thị cho ERP project bất kể `allow_billable`.

Screenshot: `12_FINDING_customer_field_hidden_on_project.png`.

---

### 🟡 Finding #3 (MEDIUM) — Chạm vào "Planned Date" (header) khiến field lõi "Expiration Date" trở thành bắt buộc, chặn Save

**Bước tái hiện:**
1. Mở Project ERP, nhập giá trị vào ô "Planned Date" (start) ở header (field `date_start` chuẩn, ghép cặp daterange với field `date`/"Expiration Date").
2. Điền dữ liệu các tab khác (Modules/Tasks/...).
3. Bấm Save.

**Expected:** Lưu thành công — `erp_delivery` không dùng field `date` (ADR-006), người dùng không cần quan tâm tới "Expiration Date".

**Actual:** Lỗi "Invalid fields: Expiration Date", chặn Save hoàn toàn, cho tới khi người dùng điền cả ô "Expiration Date" (field không có ý nghĩa gì với nghiệp vụ ERP Delivery) hoặc không chạm vào "Planned Date" (start) ở header ngay từ đầu.

**Nguyên nhân:** Field `date` (core) có `required="date_start"` (từ `addons/project/views/project_project_views.xml`, base `project.edit_project`). Vì ta không reuse `date` cho `planned_go_live` (quyết định ADR-006 — đúng đắn để tránh side-effect), nhưng chưa ẩn/vô hiệu hoá cặp field `date_start`/`date` header cho project ERP, nên ràng buộc "required pair" của core vẫn áp dụng nguyên vẹn.

**File liên quan:** `custom_addons/erp_delivery/views/project_project_views.xml` (chưa xử lý ẩn/thay thế header "Planned Date" cho project ERP).

**Mức độ ảnh hưởng:** Trung bình — gây bối rối UX, không mất dữ liệu, có cách né (không chạm "Planned Date" header, chỉ dùng `planned_go_live` ở tab Overview) nhưng không trực quan.

Screenshot: `10_FINDING_expiration_date_required_error.png`.

---

### 🟡 Finding #4 (MEDIUM) — Tab "Tasks" nhúng trong Project form không có cách đánh dấu task hoàn thành

**Bước tái hiện:**
1. Mở Project ERP → tab Tasks → thêm 1 task mandatory qua inline edit.
2. Tìm cách đánh dấu task này "Done" (điều kiện `_check_go_live_conditions` kiểm tra `is_mandatory AND NOT is_closed`) ngay trong tab này.

**Expected:** Có cách nào đó (checkbox, dropdown trạng thái, hoặc click mở form) để đóng task.

**Actual:** Cột `is_closed` bị ẩn (`column_invisible="True"`, chủ đích từ Sprint 3), không có field trạng thái/kanban-state nào khác hiển thị; click vào ô tên chỉ inline-edit cái tên, không mở form đầy đủ. Người dùng phải biết đi vòng qua smart button "Tasks" riêng (khác route với tab, dẫn tới kanban/list CHUẨN của module `project`) để mở form task thật và đổi trạng thái qua đó.

**Thêm quan sát liên quan:** Form task MỞ QUA SMART BUTTON (route chuẩn `project.task` form) **không hiển thị bất kỳ field ERP-specific nào** (`risk_level`, `progress_weight`, `is_mandatory`, `acceptance_state`, `module_line_id`, `erp_actual_hours`) — các field này CHỈ xem/sửa được qua tab nhúng trên Project form. Tức là có 2 "con đường" tới cùng 1 task, mỗi đường chỉ thấy 1 nửa thông tin.

**File liên quan:** `custom_addons/erp_delivery/views/project_project_views.xml` (tab Tasks nhúng, thiếu cột trạng thái); chưa có `project_task_views.xml` riêng để bổ sung field ERP vào form task chuẩn.

**Mức độ ảnh hưởng:** Trung bình — không chặn nghiệp vụ (vẫn làm được qua con đường khác), nhưng UX rời rạc, dễ gây nhầm lẫn cho user mới.

---

### 🟢 Finding #5 (LOW, đã xác nhận KHÔNG phải lỗi — ghi lại để tránh hiểu nhầm trong tương lai)

`erp.solution.code` UNIQUE constraint HOẠT ĐỘNG ĐÚNG qua UI (dialog "Oh snap! Solution Code must be unique" hiện ra đúng, có nút Stay here/Discard) — khác với Finding liên quan ở `res.partner.erp_code` (mục Setup note bên dưới) vì `erp.solution.code` là `UNIQUE(code)` đơn giản, không có cột `company_id` tham gia nên không gặp vấn đề NULL-uniqueness.

## 6. Setup note quan trọng (không phải lỗi sản phẩm, lỗi test fixture của chính phiên làm việc)

Trong lúc chuẩn bị, gặp 2 vấn đề do TỰ fixture chưa đúng (không phải bug
addon), ghi lại để minh bạch:

1. User test tạo qua shell ban đầu thiếu `base.group_user` ("Internal
   User") → gặp lỗi 403 ngay khi login ("You are not allowed to access
   'User' (res.users) records... allowed for... Internal User"). Đã thêm
   `base.group_user` cho các user test để phản ánh đúng user nội bộ thật —
   và chính việc thêm này đã dẫn tới phát hiện Finding #1 (vốn chỉ xuất
   hiện với user có `base.group_user`, tức là user thật).
2. Server Odoo dev (`odoo-bin` không kèm `--stop-after-init`) giữ cache
   registry (đặc biệt là ACL/group check) không tự đồng bộ ngay khi dữ liệu
   bị sửa từ một tiến trình `odoo-bin shell` RIÊNG BIỆT trong lúc server
   đang chạy — phải restart server để thấy thay đổi group/ACL phản ánh
   đúng. Đã xác nhận qua debug: dữ liệu DB đúng ngay lập tức, nhưng UI vẫn
   trả lỗi cũ cho tới khi restart. Đây là đặc điểm vận hành của môi trường
   dev (2 tiến trình Python riêng, mỗi tiến trình có registry cache
   riêng), không phải lỗi addon.
3. `ui_manager` ban đầu không thực sự được gán company_id khác — tự sửa lại
   trước khi có thể kết luận Finding #1 một cách chắc chắn (kết luận cuối
   dựa trên xác nhận qua `with_user().search()` ở tầng ORM, độc lập hoàn
   toàn với UI, không phụ thuộc fixture company nữa).

## 7. Những phần KHÔNG kiểm thử được qua UI và lý do

Danh sách dưới đây là snapshot tại thời điểm viết bản audit ban đầu;
filter/group-by, kanban và 5 tổ hợp cài đặt đã được chạy bổ sung ở mục 10.

| Phần | Lý do |
|---|---|
| 4 tổ hợp cài đặt qua UI thực tế (chỉ verify qua `-i`/test-tags ở Sprint 5) | UI test chỉ chạy trên 1 DB có cả 3 addon cùng lúc; không dựng lại UI test riêng cho từng tổ hợp cài đặt do giới hạn thời gian — đã có bằng chứng cài đặt sạch (exit 0) từ Sprint 5 cho cả 5 tổ hợp, chỉ chưa thao tác UI riêng từng tổ hợp |
| Test hiệu năng (N+1, bulk 1000 record) qua UI | Không có ý nghĩa đo qua browser — đã có test tự động đo query count ở Sprint 3/5 |
| Toàn bộ filter/search nâng cao (Green/Amber/Red health filter, group by) | Chưa đủ thời gian trong phiên này — NOT EXECUTED, cần một phiên UI test riêng nếu cần |
| Kanban view (màu sắc health badge) | Chưa chụp screenshot kanban project list — chỉ test list view |
| Responsive/mobile view | Ngoài phạm vi yêu cầu |
| Trình duyệt khác ngoài Chromium | Chỉ test Chromium headless (Playwright mặc định); không test Firefox/WebKit |

## 8. Tổng kết

| Hạng mục | Số lượng |
|---|---|
| Scenario PASS qua UI thật | 24 |
| Finding (lỗi thật, chưa sửa) | 5 (1 Critical, 2 High/Medium, 1 Medium, 1 xác nhận không phải lỗi) |
| NOT EXECUTED (có lý do rõ ràng) | 6 hạng mục, liệt kê ở mục 7 |
| Screenshot bằng chứng lưu trong repo | 14 file tại `docs/implementation/screenshots/006_ui_e2e/` |

**Kết luận quan trọng nhất**: toàn bộ 31+ test backend/ORM từ Sprint 1–5 đều
PASS và vẫn đúng ở phạm vi chúng kiểm tra (logic nghiệp vụ, computed field,
constraint, cooperative inheritance) — nhưng **Finding #1 cho thấy lớp bảo
vệ phân quyền record-rule (ADR-008) không có hiệu lực thực tế với user nội
bộ thật**, một lỗ hổng mà toàn bộ test suite ORM không thể phát hiện vì
cách tạo user test không đại diện đúng user thật. Đây là minh chứng rõ
ràng cho giá trị của kiểm thử UI/E2E độc lập với kiểm thử ORM.

## 9. Next Step

- Ưu tiên xử lý Finding #1 (CRITICAL) trước khi coi hệ thống production-ready — cần thiết kế lại cơ chế record rule hoặc bổ sung kiểm tra ở tầng khác (ví dụ `_search`/`read` override, hoặc điều chỉnh `privacy_visibility`).
- Xử lý Finding #2 (Customer field ẩn) — ảnh hưởng trực tiếp tới khả năng dùng Sales Integration.
- Đánh giá Finding #3, #4 cho backlog UX.
- Bổ sung lại test backend cho scenario #1/#2 với fixture user có `base.group_user` để test suite phản ánh đúng user thật trong tương lai.

## 10. Follow-up UI execution — 2026-10-03

Playwright/Chromium đã được chạy thật trên Odoo HTTP với DB `erp_ui_test`.
Các nghiệp vụ còn lại đã được thao tác hoàn toàn qua browser (fixture
account/company là phần duy nhất chuẩn bị ngoài browser):

| UI scenario | Kết quả |
|---|---|
| Filter Green/Amber/Red | PASS |
| Group By Health | PASS |
| Project Kanban + health badge | PASS |
| Risk `open → mitigated → closed` | PASS |
| Milestone `state` + `is_reached` | PASS |

Đã chạy thêm UI smoke matrix trên 5 DB cài sạch: core, core+sale,
core+quality, all-3 (sale trước quality), all-3 (quality trước sale). Cả 5
combo đều login được, mở action Projects và mở Project form thành công.

Matrix tái hiện Finding #2: `partner_id` hiện ở core/core+quality, nhưng
không render ở core+sale và cả hai thứ tự cài all-3. Đây là bằng chứng tái
hiện finding, không phải xác nhận requirement Customer đã đạt.

Script và JSON evidence:

- `006_ui_remaining_playwright.py` — 4 testcase nghiệp vụ còn lại.
- `006_ui_install_matrix_playwright.py` — UI smoke matrix 5 tổ hợp.
- `results_ui_remaining.json` và `results_ui_install_matrix.json`.
- 9 screenshot mới trong `screenshots/006_ui_e2e/` với prefix `remaining_`.

Môi trường execution lần này dùng PostgreSQL/Odoo tạm trong `/tmp` trên các
port 55432/8169 vì service được bàn giao không chạy trong phiên hiện tại; mã
nguồn và addon path vẫn là workspace này.
