# Báo cáo phân hệ đóng học phí iBanking

Ứng dụng mô phỏng thanh toán học phí bằng tài khoản ngân hàng, giao diện tiếng Việt, chạy cục bộ bằng Docker Compose. Người dùng đăng nhập bằng tài khoản cấp sẵn, tra MSSV của mình hoặc người khác, xác nhận điều khoản và OTP rồi theo dõi kết quả/lịch sử. Tất cả dữ liệu và email là giả lập; email chỉ được thu tại Mailpit theo yêu cầu hiện hành, không yêu cầu SMTP thật.

Tài liệu mô tả thiết kế và mã nguồn hiện có. **Baseline T00–T14 đã nghiệm thu bằng 80 ca kiểm tra qua các bộ lệnh có phạm vi riêng; các đợt giao diện sau được ghi riêng tại [biên bản kiểm chứng](VERIFICATION.md).** [Bảng đối chiếu tiêu chí](RUBRIC_AUDIT.md) tập hợp kết luận rà soát và bằng chứng chọn cho bài nộp. Toàn bộ tài liệu cần chấm nằm trong `production`.

## 1. Phân tích nghiệp vụ

Actor chính là người nộp học phí đã có tài khoản iBanking. Người nộp và sinh viên là hai vai trò độc lập: tài khoản `an` có thể trả cho MSSV `52200002`; người nhận OTP/kết quả vẫn là người nộp được Auth xác định. Tài khoản seed không có chức năng đăng ký, nạp/chuyển tiền hay quản trị.

Giao diện có ba nhóm thông tin: người nộp chỉ đọc; sinh viên/khoản thu tra theo MSSV; xác nhận điều khoản và thanh toán. Số tiền do Tuition xác định, chỉ thanh toán toàn bộ khoản hiện hành. Backend không nhận số tiền, hồ sơ hay email do client tự đặt.

| Quy tắc | Cách thực hiện |
|---|---|
| Tiền là VND nguyên | BIGINT trong DB, không dùng số thực. `available = balance - reserved >= 0`. |
| Khoản thu hợp lệ | Một khoản hiện hành mỗi sinh viên; chỉ UNPAID được giữ quyền thanh toán. |
| Đủ tiền và đồng ý điều khoản | Validate khi tạo Payment; Wallet kiểm tra lại khi reserve, không tin số dư UI. |
| Không trừ tiền khi mới lấy OTP | Payment chờ OTP chưa giữ tiền/học phí. Xác nhận hợp lệ mới bắt đầu Saga. |
| Mỗi khoản chỉ trả thành công một lần | Tuition khóa invoice và kiểm tra owner; invoice PAID không mở lại. |
| Mỗi Payment tối đa một debit | Wallet reservation/paymentId và debit/paymentId có khóa duy nhất. |
| Thất bại chỉ sau dọn reservation | ABORTING gọi hủy cả hai service; FAILED sau cả hai ACK. |
| Sau quyết định commit phải tiến tới hoàn tất | COMMITTING retry/phục hồi, không tự refund hoặc FAILED do hết lượt retry. |
| Lịch sử phản ánh giao dịch | Payment lưu snapshot người nộp, sinh viên, số tiền; trạng thái terminal phải khớp tiền/học phí. |

Xem [Use Case](../diagrams/USE_CASE.md), [nguồn UML](../diagrams/use-case.puml) và [Sequence](../diagrams/SEQUENCE.md) cho luồng chính/ngoại lệ.

## 2. Kiến trúc và dữ liệu

Năm service dùng FastAPI, SQLAlchemy 2, psycopg 3, Alembic và HTTPX trên Python 3.13. Frontend React/TypeScript/Vite được build thành static files cho Nginx. Một PostgreSQL 18 instance demo có năm database/user riêng; service không truy cập DB của nhau. Mọi liên kết xuyên service là ID logic và REST.

| Service | Dữ liệu sở hữu | Trách nhiệm |
|---|---|---|
| Auth | users | Mật khẩu Argon2, JWT RS256, hồ sơ người nộp. |
| Wallet | wallets, wallet_reservations, wallet_debits | Số dư, reserve/capture/cancel, debit duy nhất. |
| Tuition | students, invoices, tuition_reservations | Tra cứu, giữ quyền và đóng khoản thu. |
| Payment | payments, otp_challenges, payment_outbox | Snapshot, OTP, idempotency, lịch sử, Saga/outbox. |
| Notification | messages | Dedup, lưu job bền vững, SMTP retry và xóa payload. |

[ERD](../diagrams/ERD.md) liệt kê field/PK/FK/unique, CHECK và quan hệ logic không FK. Mỗi service có migration SQL tường minh trong `services/<service>/migrations/versions/0001_initial.py`; seed dùng conflict-do-nothing nên chạy lại không đặt lại số dư hoặc mở lại học phí đã trả. Startup API chạy migrate rồi seed; worker là tiến trình riêng, không tự sửa schema.

[Architecture](../diagrams/ARCHITECTURE.md) thể hiện REST nội bộ, DB, worker, outbox và Mailpit. [Compose runtime](../../compose.yaml) chỉ bind cổng web vào loopback; Nginx không route `/internal`. [Kịch bản demo](../demo/DEMO.md) hướng dẫn dùng cấu hình này với project/volume riêng. Build context chỉ chứa `production`; test và công cụ hỗ trợ được cách ly khỏi image runtime.

## 3. REST API và ranh giới tin cậy

[CONTRACT.md](../api/CONTRACT.md) là đặc tả URI/method/input/output/status và hợp đồng nội bộ. OpenAPI từng ứng dụng được sinh từ FastAPI `/openapi.json` tại service; Nginx không công khai endpoint nội bộ này. Artifact OpenAPI xuất khi bàn giao phải đối chiếu schema hiện tại.

| API công khai dưới `/api/v1` | Kết quả chính |
|---|---|
| POST `/auth/login` | Token 60 phút; sai thông tin 401. |
| GET `/me` | Hồ sơ người đang đăng nhập. |
| GET `/wallet` | balance/reserved/available, VND. |
| GET `/students/{mssv}/tuition` | Sinh viên và invoice/null; MSSV không tồn tại 404. |
| POST `/payments` | `invoiceId`, `acceptedTerms:true`, `Idempotency-Key`; tạo 201/retry 200. |
| POST `/payments/{id}/confirm` | OTP sáu chữ số; 202 khi nhận xử lý. |
| GET `/payments/{id}` | Snapshot/trạng thái; kiểm tra chủ Payment. |
| GET `/payments?page=1&pageSize=20` | Chỉ lịch sử chủ tài khoản, phân trang. |

Ngoài login, API công khai kiểm tra JWT với issuer/audience và khóa công khai. JWT subject quyết định người nộp; Auth giữ khóa ký riêng. Payment kiểm tra quyền sở hữu khi GET/confirm; người khác nhận 403. Request DTO từ chối trường ngoài hợp đồng. Service gọi API nội bộ phải có `X-Service-Key`, không tin client chỉ vì biết paymentId.

Lỗi thống nhất `{code,message,requestId}`: 400 OTP sai; 401 xác thực; 403 quyền; 404 tài nguyên; 409 xung đột nghiệp vụ/idempotency; 410 hết OTP; 422 input; 429 OTP khóa sau lần sai thứ năm. Public status gồm PENDING_OTP/PROCESSING/SUCCEEDED/FAILED/EXPIRED; không lộ checkpoint Saga.

## 4. Transaction và chứng minh concurrency

Không có transaction phân tán bao trùm HTTP. Wallet và Tuition khóa hàng trong transaction PostgreSQL ngắn. Payment ghi quyết định và checkpoint cục bộ rồi gọi REST bên ngoài transaction. Transactional outbox gắn việc tạo sự kiện email với trạng thái Payment; Notification chỉ ACK sau khi đã lưu job.

Saga: `PREPARING → reserve Tuition → reserve Wallet → COMMITTING → capture Wallet → Tuition PAID → SUCCEEDED + outbox`. Trước COMMITTING, lỗi nghiệp vụ hoặc quá 30 giây chuẩn bị chuyển ABORTING. Hủy tạo tombstone cả khi chưa có reservation để chặn reserve đến muộn. Reservation không tự hết hạn độc lập. Sau COMMITTING, worker chỉ phục hồi theo hướng hoàn tất.

| Tranh chấp / sự cố | Lập luận từ cơ chế | Kết quả cần kiểm chứng trên PostgreSQL thật |
|---|---|---|
| Một ví 10 triệu, hai khoản 6 triệu | Hai lệnh reserve cùng khóa hàng wallet; lệnh sau thấy available sau hold của lệnh trước. | Một thành công; một thất bại sạch; balance/available 4 triệu, reserved 0, một debit. |
| Hai người trả cùng invoice | Hai lệnh reserve khóa cùng invoice; owner quyết định trước mọi capture. | Một Payment thành công, chỉ một debit toàn hệ thống cho khoản đó; bên thua không mất tiền. |
| Retry capture sau mất ACK | PK debit paymentId và final reservation idempotent. | Một debit, không giảm balance lần hai. |
| Crash sau side effect trước checkpoint | Worker mới claim sau lease; gửi lại cùng ID/payload. | Đi tiếp từ checkpoint mà không lặp hiệu ứng tài chính. |
| Cancel trước reserve | Tombstone CANCELLED ngăn reserve tới muộn. | Không giữ tiền/học phí sau FAILED. |
| Worker cũ chạy sau hết lease | Token/lease được kiểm tra khi ghi checkpoint. | Worker cũ không ghi đè quyết định mới. |
| Notification lưu job nhưng mất ACK | PUT cùng eventId dedup bằng PK và request hash. | Một job; outbox retry rồi nhận ACK. |
| SMTP đã gửi nhưng crash trước SENT | Không thể transaction chung DB và SMTP. | Có thể gửi email trùng; thanh toán vẫn chỉ một debit. |

Claim công việc dùng `FOR UPDATE SKIP LOCKED`, lease 30 giây và token; worker retry backoff lũy thừa có jitter tới khoảng 30 giây. Payment/outbox và Notification giữ dữ liệu công việc trong DB nên restart không làm mất quyết định. Nếu lỗi kéo dài sau COMMITTING, Payment còn PROCESSING và cần phục hồi/đối soát; không giả định thành công khi chưa đóng invoice.

## 5. OTP, riêng tư và idempotency

OTP sáu chữ số sinh bằng `secrets`, tối đa 5 phút và 5 lần sai, gắn một Payment. Challenge lưu HMAC SHA256, không lưu mã rõ; partial unique index ngăn trùng mã ACTIVE. Collision được thử lại có giới hạn trong savepoint; không sinh được trả lỗi và rollback. Confirm khóa Payment rồi challenge; dùng OTP và chuyển PREPARING trong cùng transaction, nên hai confirm đồng thời không tạo hai Saga.

Email OTP ở outbox/job được mã hóa Fernet và xóa ciphertext sau ACK/gửi hoặc hết hạn theo từng tầng. Notification bỏ OTP quá hạn. Success event không hết hạn và được retry độc lập với kết quả tài chính. Không log/trả OTP, password, JWT, ciphertext hoặc credential SMTP. Mailpit chứa thư OTP rõ theo mục đích hộp thư demo: chỉ dùng dữ liệu giả và hạn chế truy cập máy demo.

POST Payment dùng unique `(payer_id,idempotency_key)` và fingerprint: cùng payload trả Payment cũ; payload khác trả 409. Reservation giữ payload bất biến theo paymentId; retry cùng trạng thái không tạo hiệu ứng mới, trạng thái cuối không đảo. Notification dùng eventId và request_hash kể cả sau xóa payload. Đó là idempotency ở DB/API; không phải bảo đảm email SMTP exactly-once.

## 6. Web và vận hành

Web hiển thị người nộp chỉ đọc, tra MSSV, điều khoản bắt buộc, OTP/countdown từ expiresAt, trạng thái xử lý và lịch sử. Poll hai giây lấy trạng thái server; không báo thành công chỉ vì gửi confirm xong. Khi mất response tạo Payment, client giữ idempotency key để retry. JWT nằm trong bộ nhớ UI; sessionStorage chỉ giữ ID giao dịch/attempt key phục hồi, đăng nhập lại sau reload.

Xem [hướng dẫn chạy](../../README.md) và [kịch bản demo](../demo/DEMO.md). Email local: `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`; Mailpit UI qua `/mail/`. Không cần email thật hay dịch vụ cloud. Secrets sinh cục bộ, không đưa `.env`/private key vào bài nộp; `.env.example` chỉ mô tả biến cấu hình.

Ứng dụng này mô phỏng cho học tập, chưa có đối soát vận hành ngân hàng thật, quản trị, reset mật khẩu, rate limit đăng nhập ở perimeter hay HTTPS public. Không triển khai công khai với dữ liệu thật. Không thêm broker, nạp tiền, chuyển tiền hoặc hoàn tiền tự động ngoài phạm vi.

## 7. Đối chiếu tám yêu cầu và bằng chứng

| Yêu cầu | Artifact triển khai | Kiểm chứng cần đối chiếu |
|---|---|---|
| 1. Phân tích nghiệp vụ, Use Case, ERD | Mục 1–2; [Use Case](../diagrams/USE_CASE.md), [ERD](../diagrams/ERD.md). | Khớp field/constraint và actor với source/migration. |
| 2. Microservices Architecture | [Architecture](../diagrams/ARCHITECTURE.md), năm service, Compose/Nginx. | Năm DB/role; không truy cập chéo DB; runtime chỉ web public. |
| 3. REST API đầy đủ | [Contract](../api/CONTRACT.md), FastAPI/OpenAPI. | Schema/status/JWT/ownership/idempotency tests và bản xuất OpenAPI. |
| 4. CSDL phù hợp | PostgreSQL 18, migrations, seed, [ERD](../diagrams/ERD.md). | Dựng DB sạch, migrate/seed lặp an toàn, constraint. |
| 5. Service/API nghiệp vụ | Auth/Wallet/Tuition/Payment/Notification và workers. | Login → tra cứu → điều khoản → OTP → xử lý → lịch sử; nhánh lỗi. |
| 6. Transaction/concurrency | Mục 4, [Sequence](../diagrams/SEQUENCE.md). | PostgreSQL thật: hai race, crash/lost response, dọn reserve, forward recovery. |
| 7. Web tương tác | React/Vite tiếng Việt, Nginx. | Playwright UI, bàn phím, mobile; tách test API giả lập với kiểm thử live. |
| 8. Cài đặt/sử dụng/demo | [README](../../README.md), [DEMO](../demo/DEMO.md), báo cáo/sơ đồ. | Dựng theo hướng dẫn, demo Mailpit và kịch bản lỗi/phục hồi. |

Bằng chứng được chọn cho bài nộp gồm [kết quả kiểm chứng](VERIFICATION.md), ảnh trong `images/` và [đối chiếu từng tiêu chí](RUBRIC_AUDIT.md). Log và ghi chú phát triển thô được lưu riêng ngoài bộ nộp; kết luận bên dưới chỉ áp dụng cho phạm vi và thời điểm ghi rõ.

| Gate cuối | Trạng thái đã kiểm chứng |
|---|---|
| Backend service suite |50 passed, exit0; PostgreSQL18 thật, HTTP dependency giả lập nêu rõ. |
| REST/Notification |9 ca đạt, exit0; gateway DNS sau recreate và OTP SMTP tới Mailpit, hai race tiền/học phí, email retry/restart/expiry. |
| Recovery/cách ly DB |8 ca đạt qua nhóm5+3; đủ20 cặp kết nối chéo bị từ chối. |
| Frontend baseline T00–T14 | Build đạt; 12 UI mocked cases và 1 live Nginx/API/Mailpit case đạt. Các lần mở rộng UI được ghi riêng trong VERIFICATION. |
| Review độc lập |Contract/financial/security/delivery PASS; finding quan trọng đã đóng. |
| Tài liệu/sơ đồ |5 OpenAPI;10 Mermaid render SVG; UseCase UML source; README/DEMO và ảnh luồng thật. |

Baseline có 80 ca riêng biệt; lệnh, phạm vi, giới hạn và các lần kiểm chứng bổ sung được ghi trong [VERIFICATION](VERIFICATION.md). URL demo là localhost:8080; số dư thực tế phụ thuộc giao dịch đã chạy, seed không reset dữ liệu. Kiểm thử tự động dùng stack riêng.
