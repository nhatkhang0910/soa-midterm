# ERD theo database

Bản SVG: [Auth](rendered/erd-1.svg), [Wallet](rendered/erd-2.svg), [Tuition](rendered/erd-3.svg), [Payment](rendered/erd-4.svg), [Notification](rendered/erd-5.svg).

Các bảng/field dưới đây đối chiếu `services/*/models.py` và migration khởi tạo. `PK` là khóa chính, `FK` chỉ quan hệ trong cùng database, `UK` là unique. UUID xuyên service là tham chiếu logic, **không phải FK xuyên database**. Timestamp có múi giờ; tiền dùng BIGINT VND.

## Auth — database `auth`

```mermaid
erDiagram
    users {
        varchar36 id PK
        varchar64 username UK
        text password_hash
        varchar160 full_name
        varchar24 phone
        varchar254 email
    }
```

## Wallet — database `wallet`

```mermaid
erDiagram
    wallets ||--o{ wallet_reservations : user_id
    wallets ||--o{ wallet_debits : user_id
    wallet_reservations ||--o| wallet_debits : payment_id
    wallets {
        uuid user_id PK
        bigint balance
        bigint reserved
    }
    wallet_reservations {
        uuid payment_id PK
        uuid user_id FK
        bigint amount
        varchar16 state
    }
    wallet_debits {
        uuid payment_id PK,FK
        uuid user_id FK
        bigint amount
        timestamptz created_at
    }
```

CHECK: `balance >= 0`, `0 <= reserved <= balance`, `amount > 0`; reservation có state RESERVED/CAPTURED/CANCELLED. PK `wallet_debits.payment_id` giới hạn một debit mỗi Payment. `available = balance - reserved` được tính khi trả API, không phải cột lưu riêng.

## Tuition — database `tuition`

```mermaid
erDiagram
    students ||--o| invoices : student_id
    invoices ||--o{ tuition_reservations : invoice_id
    students {
        uuid id PK
        varchar20 mssv UK
        varchar200 full_name
    }
    invoices {
        uuid id PK
        uuid student_id FK,UK
        bigint amount
        varchar16 status
        uuid reserved_payment_id UK "nullable, non-FK"
        uuid paid_payment_id UK "nullable, non-FK"
    }
    tuition_reservations {
        uuid payment_id PK
        uuid invoice_id FK
        bigint amount
        varchar16 state
    }
```

Unique `student_id` biểu diễn tối đa một khoản hiện hành/MSSV. Khoản thu UNPAID không có owner; RESERVED có `reserved_payment_id`, chưa có `paid_payment_id`; PAID không còn reservation owner. `paid_payment_id` có thể null ở dữ liệu seed đã trả. CHECK amount dương và các giá trị status/state hợp lệ. Một invoice có nhiều lần thử lịch sử, nhưng khóa hàng invoice quyết định tối đa một người thắng.

## Payment — database `payment`

```mermaid
erDiagram
    payments ||--|| otp_challenges : payment_id
    payments ||--o{ payment_outbox : payment_id
    payments {
        uuid id PK
        uuid payer_id "non-FK"
        uuid invoice_id "non-FK"
        varchar128 idempotency_key "UK with payer_id"
        varchar64 fingerprint
        bigint amount
        jsonb payer "snapshot"
        jsonb student "snapshot"
        varchar20 status
        timestamptz otp_expires_at
        timestamptz created_at
        varchar80 failure_code "nullable"
        varchar16 saga_state "nullable"
        integer checkpoint
        timestamptz prepare_deadline "nullable"
        integer attempt
        timestamptz next_attempt_at
        uuid claim_token "nullable"
        timestamptz lease_until "nullable"
        varchar80 last_error "nullable"
    }
    otp_challenges {
        uuid payment_id PK,FK
        varchar64 code_hmac "partial UK while ACTIVE"
        timestamptz expires_at
        integer attempts
        varchar12 status
    }
    payment_outbox {
        uuid id PK
        uuid payment_id FK "UK with kind"
        varchar24 kind
        varchar320 recipient
        text encrypted_payload "nullable"
        timestamptz expires_at "nullable"
        varchar12 status
        integer attempt
        timestamptz next_attempt_at
        uuid claim_token "nullable"
        timestamptz lease_until "nullable"
        varchar80 last_error "nullable"
    }
```

Unique `(payer_id,idempotency_key)` chống tạo Payment trùng; fingerprint phát hiện cùng key nhưng khác payload. Unique `(payment_id,kind)` ngăn lặp email event cùng loại. Partial unique `code_hmac WHERE status='ACTIVE'` chống mã OTP ACTIVE trùng toàn cục. CHECK `attempts BETWEEN 0 AND 5`, amount dương, status/Saga/kind hợp lệ. Index phục vụ lịch sử và công việc tới hạn; saga checkpoint nằm trong `payments`, không có bảng Saga riêng.

## Notification — database `notification`

```mermaid
erDiagram
    messages {
        varchar36 event_id PK "logical payment_outbox.id, non-FK"
        varchar32 kind
        varchar254 recipient
        varchar64 request_hash
        text encrypted_payload "nullable"
        timestamptz expires_at "nullable"
        varchar16 state
        integer attempts
        timestamptz next_attempt_at
        varchar36 claim_token "nullable"
        timestamptz lease_until "nullable"
        varchar64 last_error "nullable"
    }
```

PK event_id dedup job; request_hash so khớp retry cả khi payload đã bị xóa. State QUEUED/SENT/EXPIRED được CHECK. SMTP có thể gửi lại sau crash trước cập nhật SENT.

## Tham chiếu logic giữa service

| Nguồn | Đích logic | Cơ chế, không FK |
|---|---|---|
| wallets.user_id, payments.payer_id | users.id | JWT subject; Payment gọi hồ sơ Auth bằng REST. |
| payments.invoice_id | invoices.id | Payment đọc và reserve qua REST Tuition. |
| wallet_reservations.payment_id, tuition_reservations.payment_id | payments.id | Payment điều phối lệnh idempotent bằng ID. |
| invoices.reserved_payment_id / paid_payment_id | payments.id | Owner và kết quả thanh toán do REST cập nhật. |
| messages.event_id | payment_outbox.id | PUT nội bộ dedup bằng event ID. |

Mỗi database còn có bảng kỹ thuật `alembic_version` do Alembic quản lý; không thuộc mô hình nghiệp vụ. [Hợp đồng API](../api/CONTRACT.md) quy định chuyển trạng thái và validation không thể biểu đạt hết bằng ERD.
