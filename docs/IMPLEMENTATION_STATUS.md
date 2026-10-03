# ERP Delivery Implementation Status

## Current Status

Current Sprint: Sprint 5 (Tuần 9–10) — Quality Gate + Performance + Tests + Docs
Current Milestone: Milestone 5 (FINAL) — DONE
Last Updated: 2026-10-03

Dự án đã hoàn thành đủ 5/5 sprint theo `ERP_Delivery_Execution_Plan.md`.

## Progress

| ID | Feature | Addon | Status | Tests | Documentation |
|---|---|---|---|---|---|
| 001 | ERP Customer (res.partner) + Solution Catalog (erp.solution, erp.solution.category) | erp_delivery | DONE | PASS | DONE |
| 002 | Project Core & Workflow (project.project extension, 8-state machine, record rules) | erp_delivery | DONE | PASS | DONE |
| 003 | Module Lines, Tasks, Milestones, Risks, 10 computed fields (9 trên project.project + actual_effort trên module_line) + health_status, cron | erp_delivery | DONE | PASS | DONE |
| 004 | Go-live Base Workflow (`_check_go_live_conditions`) + Sales Integration (SO → ERP Project) | erp_delivery, erp_delivery_sale | DONE | PASS | DONE |
| 005 | Quality Gate (cooperative inheritance) + Performance audit (5 điểm) + đủ 8 test scenario + README×3 + TECHNICAL_NOTES.md | erp_delivery, erp_delivery_sale, erp_delivery_quality | DONE | PASS | DONE |

## Architecture Decisions

| ID | Decision | Reason |
|---|---|---|
| ADR-001 | 3 addons độc lập (`erp_delivery` core + `erp_delivery_sale` + `erp_delivery_quality`), Sales/Quality kết nối qua runtime check thay vì bridge module | Đáp ứng yêu cầu "cài độc lập từng gói" trong khi giới hạn tối đa 3 addon |
| ADR-002 | `erp.solution.internal_cost` dùng `Float(company_dependent=True)` + `widget="monetary"` thay vì `Monetary(company_dependent=True)` | Odoo 18 không cho phép field `Monetary` là `company_dependent` — xem `docs/implementation/001_...md` mục 11 |
| ADR-003 | `res.partner.subscription_value` dùng `currency_field` trỏ tới field compute không-store `company_currency_id` | `res.partner` chuẩn không có field `currency_id`; tránh thêm cột DB thừa |
| ADR-004 | `erp_project_ids` (res.partner → project.project) có domain lọc `is_erp_delivery=True` (resolved ở Sprint 2) | Field `is_erp_delivery` được thêm vào `project.project` ở Sprint 2 |
| ADR-005 | Tái sử dụng field chuẩn `user_id` ("Project Manager") làm ERP PM, không thêm `pm_id` song song | `project.project` đã có sẵn field cùng ngữ nghĩa; tránh duplicate field — `docs/implementation/002_...md` mục 11 |
| ADR-006 | `planned_go_live` là field mới, không tái dùng field chuẩn `date` ("Expiration Date") | `date` gắn widget daterange + logic auto-fill riêng của module `project`; tránh side-effect |
| ADR-007 | `contract_value` tái dùng `currency_id` có sẵn trên `project.project` làm `currency_field` | Khác `res.partner`, `project.project` đã có `currency_id` computed |
| ADR-008 | Record rules ERP (Consultant/Manager) luôn OR với `('is_erp_delivery', '=', False)` | Tránh rule ERP ảnh hưởng tới project thường (minimal blast radius) |
| ADR-009 | ACL mới cấp trực tiếp cho `erp_delivery.group_erp_delivery_consultant/manager`, không dùng `implied_ids` kéo `project.group_project_user/manager` | ACL chuẩn chỉ có read; `implied_ids` sẽ cấp thừa quyền Project Manager chuẩn |
| ADR-010 | `_inherit = 'project.milestone'` (model chuẩn), không tạo `erp.milestone` mới | Odoo 18 đã có sẵn model tương đương — `docs/implementation/003_...md` mục 11 |
| ADR-011 | Field mới `erp_actual_hours` trên `project.task`; không dùng `task.effective_hours`/`task.progress` | 2 field đó chỉ tồn tại khi cài `hr_timesheet` — ngoài kiến trúc 3-addon đã thống nhất |
| ADR-012 | Mọi computed field phụ thuộc task dùng field `tasks` (không domain), không dùng `task_ids` | `task_ids` có domain ẩn `is_closed=False` — phát hiện qua test thất bại thực tế |
| ADR-013 | `project.project.erp_sale_order_id` (không phải `sale_order_id` như plan) | Addon chuẩn `sale_project` định nghĩa `sale_order_id` khác ngữ nghĩa — **đã xác nhận thực tế xảy ra** khi test combo cài đặt Sprint 5 (`sale_project` auto-install khi cài `sale_management`+`erp_delivery`, cả 2 field cùng tồn tại không xung đột nhờ đổi tên) |
| ADR-014 | Bridge case check (`erp_delivery_quality`) dùng `"erp_sale_order_id" in self._fields`, không dùng `'sale.order' in self.env` như plan | Check của plan chỉ xác nhận app Sales tồn tại, không xác nhận addon `erp_delivery_sale` đã cài — rủi ro `AttributeError`; field-existence check mới chính xác — `docs/implementation/005_...md` mục 11 |
| ADR-015 | Đổi label `res.partner.company_currency_id` từ "Currency" → "ERP Subscription Currency" | Trùng label với field `currency_id` của module `account` (bị kéo theo khi cài `sale`) — phát hiện thực tế qua test 5 combination cài đặt |
| ADR-016 | Không triển khai `env.norecompute()` (Sprint 5B điểm 5 của plan) | API không tồn tại trong Odoo 18 thực tế (`grep` xác nhận); ORM đã tự batch recompute qua `@api.model_create_multi`, có test chứng minh — không tự chế framework behavior |

## Sprint 5 — Chi tiết hoàn thành

- **Addon `erp_delivery_quality`**: hoàn chỉnh — `erp.quality.criterion`,
  `erp.quality.assessment`, `project.project` extension
  (`quality_score`/`quality_threshold`/`is_quality_gate_passed`),
  cooperative inheritance `_check_go_live_conditions()`.
- **Test tất cả tổ hợp addon**: 5 lần cài thật trên DB riêng — core /
  core+sale / core+quality / all3 (sale→quality) / all3 (quality→sale) —
  cả 5 `EXIT=0`, không ERROR/CRITICAL.
- **Performance audit**: 5 điểm đầy đủ (N+1 list, `_read_group` dashboard,
  prefetch `mapped()`, 4 index bổ sung, bulk-import behavior) — mỗi điểm
  có test đo `sql_log_count` thật, không suy luận lý thuyết.
- **8/8 test scenario của đề**: chạy thật và PASS — xem bảng đầy đủ ở
  `docs/implementation/005_quality_gate_performance_docs.md` mục 9.
- **`TECHNICAL_NOTES.md`**: 12 câu hỏi giải trình kỹ thuật, cooperative
  inheritance pattern, bridge case, 3 (+2) điểm tối ưu performance.
- **`README.md`** cho cả 3 addon + cập nhật README gốc.
- Install/upgrade/uninstall: chạy thật, PASS (xem
  `docs/implementation/005_...md` mục 10).

## Post-Sprint 5 — UI/E2E follow-up (2026-10-03)

- Playwright Chromium chạy thật trên Odoo HTTP: 4/4 testcase còn lại PASS —
  filter/group-by Health, Kanban health badge, Risk lifecycle và Milestone
  state/is_reached.
- UI smoke matrix 5/5 tổ hợp cài đặt PASS ở mức login/action/form smoke.
- Matrix tái hiện Finding #2: `partner_id` hiện ở core/core+quality nhưng ẩn
  ở core+sale và cả hai thứ tự cài all-3. Finding này chưa được sửa.
- Evidence: `docs/implementation/results_ui_remaining.json`,
  `docs/implementation/results_ui_install_matrix.json` và screenshot prefix
  `remaining_` trong `docs/implementation/screenshots/006_ui_e2e/`.
- Các Finding #1–#4 trong tài liệu UI E2E vẫn là backlog chưa sửa.

## Known Limitations (toàn dự án)

- Demo data đầy đủ theo checklist (2 companies, 3 customers, 5 solutions, 3
  projects, 6 module lines, 10 tasks, 2 SO, 3 users) — chưa tạo, không nằm
  trong phạm vi được giao cho Sprint 5 lần này.
- UI/E2E follow-up mới chỉ chạy Chromium headless; chưa test Firefox/WebKit,
  responsive/mobile và test hiệu năng qua browser.
- `pylint-odoo`: còn 3 warning `manifest-required-author` (1/addon), quy
  ước OCA không áp dụng cho dự án nội bộ — chấp nhận giữ nguyên xuyên suốt
  5 sprint.
