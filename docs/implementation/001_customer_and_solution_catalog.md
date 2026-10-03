# ERP Customer & Solution Catalog (Sprint 1 — Foundation & Data Model)

## 1. Mục tiêu

Có addon `erp_delivery` cài được, mở rộng `res.partner` thành ERP Customer,
và một danh mục giải pháp ERP (`erp.solution` / `erp.solution.category`)
hoạt động với phân quyền 3 vai trò (User / Consultant / Manager).

## 2. Requirement liên quan

`ERP_Delivery_Execution_Plan.md`, mục 3 — **Sprint 1 (Tuần 1–2): Foundation &
Data Model**, và mục 2.1.1 (bảng model chi tiết addon `erp_delivery`).

## 3. Trạng thái trước khi thay đổi

Repository chỉ có 3 thư mục rỗng `custom_addons/erp_delivery`,
`custom_addons/erp_delivery_sale`, `custom_addons/erp_delivery_quality` —
chưa có file nào. Không có gì để audit/tái sử dụng.

## 4. Thiết kế

### Models

- `res.partner` (`_inherit`): thêm các field ERP Customer.
- `erp.solution.category` (mới): master data danh mục giải pháp.
- `erp.solution` (mới, `_inherit = ['mail.thread']`): catalog giải pháp ERP.

### Fields

**`res.partner`**

| Field | Type | Purpose | Store | Index |
|---|---|---|---|---|
| `is_erp_customer` | Boolean | Đánh dấu contact là khách hàng ERP | ✅ | ✅ |
| `erp_code` | Char | Mã khách hàng ERP, unique theo company | ✅ | ✅ |
| `erp_tier` | Selection (bronze/silver/gold/platinum) | Hạng khách hàng | ✅ | ❌ |
| `contract_end_date` | Date | Ngày hết hạn hợp đồng | ✅ | ❌ |
| `expected_users` | Integer | Số user dự kiến | ✅ | ❌ |
| `company_currency_id` | Many2one (res.currency) | **Kỹ thuật** — currency hiển thị cho `subscription_value` (res.partner không có currency_id sẵn) | ❌ (compute, không store) | ❌ |
| `subscription_value` | Monetary | Giá trị subscription, chỉ Manager thấy | ✅ | ❌ |
| `erp_project_ids` | One2many → `project.project` (qua `partner_id`) | Danh sách dự án ERP của khách hàng | — | — |

**`erp.solution.category`**

| Field | Type | Purpose | Store | Index |
|---|---|---|---|---|
| `name` | Char | Tên danh mục | ✅ | ❌ |
| `code` | Char | Mã danh mục, unique | ✅ | ❌ (unique constraint đã implicit index) |
| `sequence` | Integer | Thứ tự hiển thị | ✅ | ❌ |

**`erp.solution`**

| Field | Type | Purpose | Store | Index |
|---|---|---|---|---|
| `code` | Char | Mã giải pháp, unique | ✅ | ❌ |
| `name` | Char (translate) | Tên giải pháp | ✅ | ❌ |
| `description_short` | Char (translate) | Mô tả ngắn | ✅ | ❌ |
| `description_rich` | Html (translate) | Mô tả chi tiết | ✅ | ❌ |
| `category_id` | Many2one → `erp.solution.category` | Danh mục | ✅ | ❌ |
| `active` | Boolean | Archive | ✅ | ❌ |
| `standard_effort` | Float | Effort chuẩn (giờ) | ✅ | ❌ |
| `currency_id` | Many2one (res.currency) | Currency của solution (default = company currency) | ✅ | ❌ |
| `service_price` | Monetary | Giá bán dịch vụ | ✅ | ❌ |
| `internal_cost` | Float, `company_dependent=True` | Chi phí nội bộ, khác nhau theo company, chỉ Manager thấy | ✅ (company-dependent storage) | btree_not_null (tự động) |
| `image` | Binary | Hình ảnh | ✅ (attachment) | — |
| `document_ids` | Many2many → `ir.attachment` | Tài liệu đính kèm | — | — |

### Relationships

- `res.partner (1) ←→ (N) project.project` qua field chuẩn `partner_id` của
  `project.project` (field này đã có sẵn từ module `project`). Field
  `erp_project_ids` trên `res.partner` chỉ là nghịch đảo One2many, không tạo
  cột DB mới.
- `erp.solution.category (1) ←→ (N) erp.solution` qua `category_id`.
- `erp.solution (N) ←→ (N) ir.attachment` qua `document_ids`.

### Business Rules

- `erp_code` unique theo `(erp_code, company_id)` — SQL constraint, cho phép
  cùng mã ở 2 company khác nhau nhưng không trùng trong 1 company.
- `erp.solution.code` unique toàn hệ thống.
- `erp.solution.category.code` unique toàn hệ thống.
- `internal_cost` và `subscription_value` chỉ nhóm Manager
  (`erp_delivery.group_erp_delivery_manager`) mới đọc/ghi được (field-level
  group, không chỉ ẩn trên view).

### Workflow

Không áp dụng cho Sprint 1 (chưa có state machine — sẽ thêm ở Sprint 2 cho
`project.project`).

## 5. Files thay đổi

| File | Thay đổi |
|---|---|
| `custom_addons/erp_delivery/__manifest__.py` | Mới |
| `custom_addons/erp_delivery/__init__.py` | Mới |
| `custom_addons/erp_delivery/models/__init__.py` | Mới |
| `custom_addons/erp_delivery/models/res_partner.py` | Mới |
| `custom_addons/erp_delivery/models/erp_solution_category.py` | Mới |
| `custom_addons/erp_delivery/models/erp_solution.py` | Mới |
| `custom_addons/erp_delivery/security/erp_delivery_security.xml` | Mới |
| `custom_addons/erp_delivery/security/ir.model.access.csv` | Mới |
| `custom_addons/erp_delivery/data/ir_sequence_data.xml` | Mới |
| `custom_addons/erp_delivery/data/solution_category_data.xml` | Mới |
| `custom_addons/erp_delivery/views/res_partner_views.xml` | Mới |
| `custom_addons/erp_delivery/views/erp_solution_views.xml` | Mới |
| `custom_addons/erp_delivery/views/erp_delivery_menus.xml` | Mới |
| `custom_addons/erp_delivery/tests/__init__.py` | Mới |
| `custom_addons/erp_delivery/tests/test_customer_and_solution.py` | Mới |
| `README.md` (repo root) | Mới |

## 6. Giải thích implementation

```
User mở Contact form, tick "ERP Customer" (field cạnh Tags)
    ↓
Tab "ERP Info" trở nên visible (invisible="not is_erp_customer")
    ↓
User nhập erp_code / erp_tier / contract_end_date / expected_users
    ↓
ORM write() → SQL constraint UNIQUE(erp_code, company_id) kiểm tra ở DB level
    ↓
Chatter (mail.thread trên erp.solution) ghi lại thay đổi solution catalog
```

```
Menu ERP Delivery → Configuration → Solutions
    ↓
Tạo erp.solution, chọn category_id, nhập service_price / internal_cost
    ↓
ACL + field groups quyết định ai thấy internal_cost (chỉ Manager)
    ↓
with_company(company_b) → internal_cost trả về giá trị khác (company_dependent storage)
```

## 7. Security

- **Groups**: `group_erp_delivery_user` ⊂ `group_erp_delivery_consultant` ⊂
  `group_erp_delivery_manager` (qua `implied_ids`), dưới
  `module_category_erp_delivery`.
- **ACL** (`ir.model.access.csv`): User/Consultant đọc được `erp.solution` và
  `erp.solution.category`; chỉ Manager có quyền create/write/unlink.
- **Field Security**: `internal_cost` (erp.solution) và `subscription_value`
  (res.partner) có `groups="erp_delivery.group_erp_delivery_manager"` — đây
  là ACL thật, không phải chỉ ẩn trên view. Đọc field này bằng user không có
  quyền sẽ raise `AccessError` nếu field được yêu cầu tường minh trong
  `read()`.
- **Record Rules**: Chưa cần ở Sprint 1 (không có model nào cần phân biệt
  dữ liệu theo user/company). Sẽ bổ sung ở Sprint 2 khi `project.project`
  được extend.
- **Multi-company**: `erp_code` unique theo `(erp_code, company_id)`.
  `internal_cost` company-scoped qua `company_dependent=True`.

## 8. Performance

- `is_erp_customer`, `erp_code` trên `res.partner`: indexed — phục vụ filter
  "ERP Customers" trên search view và tra cứu theo mã khách hàng.
- `internal_cost` dùng `company_dependent=True` → Odoo tự thêm
  `index='btree_not_null'`.
- Chưa có computed field aggregate/batch trong sprint này — N+1 và
  `_read_group` sẽ được đánh giá từ Sprint 3 khi có `module_line_ids` /
  `task_ids`.

## 9. Tests

| Test | Scenario | Expected |
|---|---|---|
| `test_erp_code_duplicate_raises_integrity_error` | Tạo 2 `res.partner` với cùng `erp_code` và cùng `company_id` | Raise `psycopg2.IntegrityError` |
| `test_consultant_cannot_read_internal_cost` | User chỉ có nhóm Consultant gọi `read(['name', 'internal_cost'])` trên `erp.solution` | Raise `AccessError`; `read(['name'])` không raise và không có `internal_cost` trong kết quả |
| `test_internal_cost_is_company_dependent` | Set `internal_cost` khác nhau qua `with_company(company_a)` / `with_company(company_b)` | Mỗi company đọc lại đúng giá trị đã set cho company đó |

## 10. Validation Result

### Executed

```bash
# Fresh DB
createdb -h /var/run/postgresql -p 5433 erp_delivery_test

# Install + run unit tests
/home/pc/odoo-dev/odoo-venv/bin/python3 /home/pc/odoo-dev/odoo/odoo-bin \
  --addons-path="/home/pc/odoo-dev/odoo/addons,/home/pc/odoo-dev/odoo/odoo/addons,/home/pc/odoo-dev/erp-delivery/custom_addons" \
  -d erp_delivery_test --db_host=/var/run/postgresql --db_port=5433 --db_user=pc \
  -i erp_delivery --test-enable --test-tags /erp_delivery --stop-after-init

# Upgrade (idempotency check)
... -u erp_delivery --stop-after-init

# Uninstall (via odoo-bin shell, button_immediate_uninstall)
... shell -d erp_delivery_test ...

# Lint
pip install pylint-odoo
python3 -m pylint --load-plugins=pylint_odoo -d all -e odoolint custom_addons/erp_delivery
```

### Result

**PASS**

- Install: `0 modules loaded in 29.12s... 39 modules loaded` — không có log
  ERROR/CRITICAL thuộc về `erp_delivery` (một cảnh báo RST "Unexpected
  indentation" xuất hiện trong quá trình load module `mail`/`base`, trước khi
  `erp_delivery` được nạp — không liên quan tới module này).
- Tests: `odoo.tests.result: 0 failed, 0 error(s) of 3 tests when loading
  database 'erp_delivery_test'`.
- Upgrade (`-u erp_delivery`): exit code 0, không log ERROR/CRITICAL.
- Uninstall: `button_immediate_uninstall()` → `state: uninstalled`, không
  exception.
- `pylint-odoo` (`-e odoolint`, rated all messages as errors for this pass):
  9.73/10 — 2 cảnh báo còn lại là quy ước đặc thù của OCA
  (`manifest-required-author`, `missing-readme`), xem mục 11 bên dưới.

**NOT EXECUTED** — kiểm thử thủ công qua UI trình duyệt thật (tạo ERP
customer, tạo solution, đổi company thấy `internal_cost` đổi). Môi trường
hiện tại không có trình duyệt. Hành vi tương đương đã được xác nhận bằng
test tự động (`test_internal_cost_is_company_dependent`) chạy trực tiếp qua
ORM, và bằng việc kiểm tra view XML parse thành công khi load module (nếu
view sai field/xpath thì module sẽ fail install — đã test ở bước Install).

## 11. Technical Decisions

### Decision

`internal_cost` trên `erp.solution` dùng `fields.Float(company_dependent=True)`
thay vì `fields.Monetary(company_dependent=True)` như execution plan mô tả,
và hiển thị bằng `widget="monetary"` trong view.

### Reason

Execution plan (mục 2.1.1) yêu cầu `internal_cost` là `Monetary,
company_dependent=True`. Khi cài module, Odoo 18 raise cảnh báo và assertion
lỗi: `company_dependent field erp.solution.internal_cost is not one of the
allowed types` — `odoo/fields.py` (`COMPANY_DEPENDENT_FIELDS`) chỉ cho phép
`char, float, boolean, integer, text, many2one, date, datetime, selection,
html` cho field `company_dependent=True`. `Monetary` không nằm trong danh
sách này ở Odoo 18. Đây là xung đột giữa tài liệu dự án và framework chuẩn —
theo nguyên tắc kiểm chứng framework và ưu tiên cách triển khai an toàn khi tài liệu dự án
và Odoo standard có vẻ xung đột", ưu tiên cách triển khai an toàn, đúng
framework.

### Alternative considered

1. Giữ `Monetary` + `company_dependent=True` → **loại** vì chặn cứng ở
   `odoo/fields.py`, không cài được module.
2. Bỏ `company_dependent`, dùng `Monetary` thường + field `company_id` trên
   `erp.solution` (solution thuộc về 1 company cụ thể) → **loại** vì solution
   catalog cần dùng chung cho mọi company (shared master data), và plan rõ
   ràng muốn "cùng 1 solution, giá internal_cost khác nhau theo company xem".
3. **Chọn**: `Float(company_dependent=True)` + `widget="monetary"` trong view
   (tham chiếu `currency_id` của chính solution qua
   `options="{'currency_field': 'currency_id'}"`) — giữ đúng ý định nghiệp vụ
   (cost khác nhau theo company context) và vẫn hiển thị đúng định dạng tiền
   tệ cho người dùng.

### Why rejected

Phương án 1 vi phạm ràng buộc kỹ thuật cứng của framework. Phương án 2 làm
sai lệch bản chất dữ liệu (solution không còn là catalog dùng chung).

---

### Decision

`res.partner.subscription_value` dùng `currency_field="company_currency_id"`
với `company_currency_id` là field Many2one **compute, không store**, thay vì
dùng `currency_id` trực tiếp như draft ban đầu trong code.

### Reason

`res.partner` chuẩn của Odoo **không có field `currency_id`**. Khai báo
`Monetary(currency_field="currency_id")` mà không có field đó trên model sẽ
raise `AssertionError: Field res.partner.subscription_value with unknown
currency_field 'currency_id'` khi load registry — xác nhận thực tế bằng chạy
thử install (xem log lần đầu tiên).

### Alternative considered

1. Thêm field `currency_id` thật (stored) lên `res.partner` → **loại**: thừa
   cột DB cho mọi partner (hàng triệu row) chỉ để phục vụ 1 field Monetary
   hiếm dùng, trong khi plan không yêu cầu field này.
2. **Chọn**: field compute không lưu trữ `company_currency_id`, trả về
   `env.company.currency_id` — không tốn storage, đúng ngữ nghĩa ("tiền tệ
   hiển thị theo company hiện tại").

### Why rejected

Phương án 1 vi phạm nguyên tắc tránh field thừa (mục 4.4 master prompt) và
không cần thiết vì toàn bộ khách hàng ERP trong hệ thống này dùng tiền tệ
theo company, không phải tiền tệ cố định theo từng partner.

---

### Decision

`erp_project_ids` trên `res.partner` dùng One2many **không có domain** lọc
`is_erp_delivery=True` (khác với execution plan mục 2.1.1 gợi ý ngầm field
này chỉ hiển thị project ERP).

### Reason

`is_erp_delivery` là field sẽ được thêm vào `project.project` ở **Sprint 2**
(mục 3, Sprint 2). Thêm domain tham chiếu field chưa tồn tại sẽ raise lỗi khi
field được dùng trong view hoặc search. Nhiệm vụ hiện tại giới hạn ở Sprint 1
("Không làm trước Sprint 2").

### Alternative considered

1. Thêm luôn field `is_erp_delivery` vào `project.project` ở Sprint 1 để
   domain hoạt động ngay → **loại**: vi phạm rõ ràng yêu cầu "Không làm trước
   Sprint 2" và mở rộng model `project.project` là nhiệm vụ của Sprint 2.
2. **Chọn**: field O2m không domain ở Sprint 1 (hiển thị tất cả project —
   kể cả project thường — của khách hàng), domain sẽ được bổ sung trong
   Sprint 2 khi `is_erp_delivery` tồn tại.

### Why rejected

Phương án 1 lấn phạm vi sprint kế tiếp.

---

### Decision

`ir.model.access.csv` chỉ cấp `perm_read` cho group User/Consultant trên cả
`erp.solution` và `erp.solution.category`; `perm_write/create/unlink` chỉ
cấp cho Manager.

### Reason

Execution plan Sprint 1 chỉ nói "ir.model.access.csv cho erp.solution và
erp.solution.category với 3 groups" mà không chỉ rõ mức quyền từng group.
Solution catalog là master data ảnh hưởng tới pricing — để Consultant/User
chỉnh sửa tự do có rủi ro business (sai giá bán, sai effort chuẩn ảnh hưởng
nhiều dự án).

### Alternative considered

1. Cho Consultant full CRUD → **loại**: rủi ro toàn vẹn dữ liệu giá/catalog
   dùng chung nhiều dự án.
2. **Chọn**: Read-only cho User/Consultant, full CRUD cho Manager.

### Why rejected

Phương án 1 không có cơ sở yêu cầu rõ ràng và rủi ro cao hơn lợi ích.

## 12. Known Limitations

- `erp_project_ids` trên `res.partner` chưa lọc theo `is_erp_delivery`
  (xem Technical Decision ở trên) — sẽ cập nhật domain ở Sprint 2.
- Chưa test kịch bản UI thật qua trình duyệt (môi trường không có browser).
- `pylint-odoo` còn 2 cảnh báo thuộc quy ước xuất bản OCA
  (`manifest-required-author`, `missing-readme`) — không áp dụng cho dự án
  nội bộ không publish lên OCA; chấp nhận giữ nguyên, không fake author OCA.
- Chưa có record rule nào trên `erp.solution`/`res.partner` (không cần ở
  Sprint 1 theo plan); multi-company isolation cho `project.project` sẽ đến ở
  Sprint 2.

## 13. Next Step

Sprint 2: inherit `project.project` với 15+ field ERP (code, pm_id,
member_ids, state machine 8 state, v.v.), sequence `erp.project.code`
(đã seed sẵn data ở Sprint 1), record rules Consultant/Manager, và bổ sung
domain `is_erp_delivery=True` cho `erp_project_ids`.
