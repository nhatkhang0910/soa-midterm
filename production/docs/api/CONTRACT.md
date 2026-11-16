# Hợp đồng triển khai v1

Đặc tả API và quy tắc xử lý của năm service trong bộ nộp. Thiết kế tổng thể ở [báo cáo](../report/REPORT.md); các bản OpenAPI JSON trong cùng thư mục mô tả schema và HTTP status của từng service.

## Nền chạy và kiểu dữ liệu

Python 3.13, FastAPI/Pydantic 2, SQLAlchemy 2 async + psycopg 3, PostgreSQL 18. Package mỗi service: `auth`, `wallet`, `tuition`, `payment`, `notification`; import helper `common` từ production/services. Một AsyncSession riêng mỗi request/task; transaction ngắn, không gọi HTTP/SMTP trong transaction. Timestamp UTC aware, UUID dạng chuỗi trong JSON, BIGINT VND. DTO extra=forbid. Public response camelCase.

Common cung cấp `Base`, `Session`, `engine`, `utcnow`, `create_app(name)`, `ApiError(status, code, message)`, `current_user` (JWT sub UUID), `require_payment` (X-Service-Key so với PAYMENT_SERVICE_KEY), `require_notification` không cần: chỉ Payment được gọi Notification; `internal_profile` dùng PAYMENT_SERVICE_KEY. JWT RS256, Auth ký bằng JWT_PRIVATE_KEY, service verify JWT_PUBLIC_KEY, iss=ibanking, aud=ibanking-web, ttl=60 phút. Env secret bắt buộc, không default secret. API lỗi JSON `{code,message,requestId}`, validation 422, JWT 401; Nginx không route /internal. Public `GET /health` kiểm tra DB; mọi service route public đầy đủ tiền tố /api/v1.

Seed mặc định lặp an toàn: user UUID `00000000-0000-0000-0000-000000000001` username `an`, user UUID `00000000-0000-0000-0000-000000000002` username `binh`, password từ DEMO_PASSWORD (mặc định được ghi README, dữ liệu giả). Email seed từ DEMO_EMAIL_AN/BINH, tên Nguyễn Văn An/Trần Thanh Bình. Wallet mỗi người balance 10000000 reserved 0. MSSV `52200001`, `52200002` mỗi người học phí 6000000 UNPAID; invoice UUID `10000000-0000-0000-0000-000000000001` và `...0002`; `52200003` PAID invoice `...0003`; `52200004` không học phí. Invoice hiện hành duy nhất theo studentId.

Mỗi service có models.py, app.py, seed.py (`python -m <service>.seed`), migrations/env.py + versions/0001_initial.py (Alembic explicit DDL), OpenAPI được xuất sau triển khai. Common migration runner: `python -m common.migrate`, env SERVICE_NAME và DATABASE_URL. Migration và seed tự chạy khi API khởi động theo [hướng dẫn cài đặt](../../README.md).

## Public API

- POST `/api/v1/auth/login` `{username,password}` →200 `{accessToken,tokenType:"bearer",expiresIn:3600}`; sai 401.
- GET `/api/v1/me` →200 `{id,fullName,phone,email}`.
- GET `/internal/users/{userId}` (Payment key) → cùng profile, 404 nếu không có.
- GET `/api/v1/wallet` →200 `{balance,reserved,available,currency:"VND"}` từ sub; không có 404.
- GET `/api/v1/students/{mssv}/tuition` →200 `{student:{id,mssv,fullName},invoice:{id,amount,currency:"VND",status:"UNPAID"|"RESERVED"|"PAID"}|null}`; MSSV không có 404. JWT bắt buộc. GET `/internal/invoices/{invoiceId}` trả `{id,amount,currency,status,student:{id,mssv,fullName}}` cho Payment. GET `/internal/wallets/{userId}` cho Payment trả như wallet.
- POST `/api/v1/payments` header Idempotency-Key (1–128 ký tự) body `{invoiceId,acceptedTerms:true}` →201 `{id,status:"PENDING_OTP",amount,currency:"VND",otpExpiresAt,payer:{id,fullName,phone,email},student:{id,mssv,fullName},createdAt,failureCode:null}`. Input thiếu/terms false 422; invoice paid/reserved/thiếu tiền 409. Backend lấy profile/amount từ service, không nhận email/amount/payer. Có cùng (payerId,key) và payload trả200 cùng Payment; khác payload 409 IDEMPOTENCY_CONFLICT, kể cả race. Outbox OTP được ghi cùng Payment/challenge. Tạo Payment không giữ tiền/học phí.
- POST `/api/v1/payments/{id}/confirm` `{otp:"123456"}` →202 Payment với status PROCESSING. OTP sai 400 OTP_INVALID; hết hạn 410 OTP_EXPIRED; khóa sau lần sai thứ 5 trả429 OTP_LOCKED; đã PROCESSING/SUCCEEDED retry trả202/200 trạng thái hiện tại không tạo hiệu ứng mới; FAILED/EXPIRED 409. Ownership sai 403, thiếu404.
- GET `/api/v1/payments/{id}` →200 Payment. Public status PENDING_OTP|PROCESSING|SUCCEEDED|FAILED|EXPIRED, internal saga state được ẩn.
- GET `/api/v1/payments?page=1&pageSize=20` →200 `{items:[Payment],page,pageSize,total}` chỉ chủ tài khoản, createdAt desc,id tie-break, pageSize1–100.

## REST nội bộ reservation

Header X-Service-Key=PAYMENT_SERVICE_KEY; chỉ Payment gọi Wallet/Tuition/Notification/Auth internal. Tất cả body UUID/string + VND integer>0, payload bất biến cho paymentId. GET chưa có trả404.

Wallet PUT `/internal/reservations/{paymentId}` `{userId,amount,state:"RESERVED"|"CAPTURED"|"CANCELLED"}` →200 `{paymentId,userId,amount,state}`. GET trả cùng object. Reserve atomic khóa wallet + reservation, available>=amount. Capture chỉ từ RESERVED, atomic balance-=amount,reserved-=amount,debit unique(paymentId). CANCELLED trước reserve tạo tombstone (không giảm số dư nếu chưa hold). Trạng thái cuối không đảo; duplicate cùng state trả200, reserve lặp khi CAPTURED/CANCELLED trả409 RESERVATION_FINAL, capture khi CANCELLED409, cancel CAPTURED409. Bất kỳ mismatch userId/amount trả409. CHECK balance>=0,reserved>=0,reserved<=balance.

Tuition PUT cùng URI `{invoiceId,amount,state:"RESERVED"|"PAID"|"CANCELLED"}` →200 `{paymentId,invoiceId,amount,state}`. GET cùng object. Khóa invoice + attempt theo thứ tự ổn định; chỉ UNPAID chưa owner mới reserve, amount phải bằng invoice.amount; RESERVED cùng paymentId idempotent; PAID chỉ owner reservation. Một invoice một người thắng; CANCELLED trước reserve tạo tombstone. Cancel PAID409; reserve sau CANCELLED409; không mở lại invoice khi PAID. Attempt/paymentId unique, invoice.paidPaymentId unique nullable. Nhánh từ chối reserve do invoice owner khác/đã paid không được mất khả năng cancel attempt của mình.

## OTP

secrets.randbelow(1000000) format 06d; HMAC SHA256(OTP_HMAC_KEY, code) duy nhất toàn cục cho ACTIVE bằng partial unique index (status='ACTIVE'). Tạo lại tối đa20 lần khi collision (savepoint), trước đó expire mã cũ. Hết pool trả503 OTP_UNAVAILABLE rollback toàn bộ. challenge paymentId unique, expiresAt=now+5 phút, attempts<=5, trạng thái ACTIVE/USED/EXPIRED/LOCKED. Confirm khóa payment rồi challenge; consume ACTIVE và PREPARING cùng local transaction. Mã hết hạn/locked không được reuse; OTP sai payment khác không làm thanh toán.

Payload email OTP dùng Fernet(EMAIL_ENCRYPTION_KEY), cùng key ở Payment/Notification; chỉ encrypted text trong DB. Email job payload được xóa sau SMTP thành công/hết hạn. Lưu fingerprint SHA256 của request gốc để duplicate sau khi xóa payload vẫn so khớp được; không đưa fingerprint vào log/API. Không log/return OTP, password, JWT, ciphertext hoặc SMTP credentials.

Khi challenge hết hạn, chuyển Payment còn PENDING_OTP thành EXPIRED. Khi sai lần thứ5, challenge LOCKED và Payment FAILED với failureCode OTP_LOCKED. Worker cleanup và GET/confirm phải áp dụng chuyển trạng thái nhất quán, khóa payment rồi challenge. OTP đã USED không bị cleanup đổi Payment đang PROCESSING. Không có resend trong v1; tạo giao dịch mới khi OTP hết hạn/khóa.

## Saga và workers

Payment lưu sagaState PREPARING/COMMITTING/ABORTING, checkpoint và prepareDeadline=now+30s. Worker claim bằng UPDATE/SELECT FOR UPDATE SKIP LOCKED + claimToken UUID, leaseUntil=now+30s, nextAttemptAt; transaction commit trước HTTP; updates compare claimToken. Lease phục hồi không xóa reservation. HTTP timeout5s, exponential backoff1–30s+jitter, lỗi kéo dài ghi code+attempt, không log payload.

PREPARING: reserve Tuition → reserve Wallet → CAS ghi COMMITTING (chỉ trước deadline). Lỗi nghiệp vụ hoặc deadline chuyển ABORTING. Không suy diễn side effect thất bại từ timeout; retry/query cùng paymentId. ABORTING: cancel cả Wallet và Tuition (kể cả chưa reserve) → FAILED chỉ sau cả hai ACK. COMMITTING: capture Wallet → mark PAID Tuition → SUCCEEDED + outbox event trong một transaction. Không abort/refund từ COMMITTING; invariant unexpected giữ PROCESSING và retry với cảnh báo cần đối soát. Stale worker không được đổi quyết định saga; command đến trễ bị tombstone/final-state chặn.

Outbox Payment: id/eventId unique, payload encrypted, expiresAt nullable, nextAttemptAt/attempt/lease/token. Event `OTP` có expiresAt; `PAYMENT_SUCCEEDED` không hết hạn. Worker chuyển PUT `/internal/messages/{eventId}` `{kind:"OTP"|"PAYMENT_SUCCEEDED",recipient,encryptedPayload,expiresAt}`. Payload OTP giải mã JSON `{otp,paymentId,amount,studentName}`; success `{paymentId,amount,studentName}`. Notification lưu/dedup trước trả200 `{eventId,status:"QUEUED"|"SENT"|"EXPIRED"}`, duplicate cùng payload phải không thêm job, mismatch409; outbox đánh delivered và xóa payload chỉ sau ACK. Quá hạn OTP xóa payload cả outbox/job. Notification worker claim/lease/retry như Payment, SMTP dùng stdlib ngoài event loop; SMTP STARTTLS bắt buộc trừ Mailpit local dev. SMTP crash có thể gửi trùng, không exactly-once.

## Kiểm thử và runtime

pytest/HTTPX/PostgreSQL thật, Playwright ngoài source. Common settings env không chứa test fault hook. Fault injection proxy/test doubles HTTP nằm non-prod. Test database/volume tách runtime, không reset seed runtime trong test. Migration/seed lặp an toàn; test concurrency dùng connection/session riêng. Docker context production, runtime không có pytest/Playwright. Health/structured logs requestId, không secret; UI keyboard/focus/loading/errors, countdown theo expiresAt, poll2s.
