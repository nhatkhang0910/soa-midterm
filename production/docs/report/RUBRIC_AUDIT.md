# Đối chiếu tiêu chí đánh giá đồ án SOA

Ngày rà soát: **16/11/2026**, Asia/Saigon. Nguồn tiêu chí: ảnh bảng chấm do người dùng cung cấp, tổng **10 điểm**. Phạm vi: bản mô phỏng iBanking cục bộ, dữ liệu seed, email SMTP tới Mailpit.

**Có đủ hiện thực và tài liệu cho cả tám nhóm tiêu chí, nhưng chưa xác nhận đạt hết.** Lượt mới có timeout gateway (chạy riêng lại đã đạt) và một ca recovery kỳ vọng SUCCEEDED nhưng kết thúc FAILED/PREPARE_TIMEOUT. Đối soát ca recovery không có ghi nợ, reservation đã dọn và học phí còn UNPAID; chưa chứng minh mất tiền, nhưng chưa tái xác nhận được nhánh phục hồi thành công của test. Đây là đánh giá kỹ thuật, không cam kết trọn 10/10; điểm cuối do giảng viên chấm, bao gồm phần trình bày trực tiếp của nhóm.

Toàn bộ đầu ra dùng để chấm nằm trong `production`: source, cấu hình chạy, migration/seed, OpenAPI, UML/ERD/Architecture/Sequence, README, báo cáo, ảnh và bằng chứng đã chọn. Mọi liên kết file trong tài liệu này nằm trong bộ nộp. Test/fixture/log thô thuộc workspace phát triển; không cần các file đó để đọc bảng đối chiếu hoặc chạy demo theo hướng dẫn.

## 1. Đối chiếu từng phần điểm

“Đạt” dưới đây là đánh giá kỹ thuật từ source, tài liệu và kiểm chứng có phạm vi ghi ở mục 2; không phải cam kết điểm số.

| Nhóm / điểm tối đa | Phần yêu cầu trong ảnh | Đánh giá | Đầu ra trong production |
|---|---|---|---|
| 1. Nghiệp vụ & UML — 1,0 | 0,5: Use Case đúng actor và chức năng chính | Đạt | [Use Case](../diagrams/USE_CASE.md), [ảnh UML](../diagrams/rendered/use-case-uml.svg), [nguồn PlantUML](../diagrams/use-case.puml): người nộp, hệ email, đăng nhập, tra cứu, thanh toán/trả hộ, điều khoản, OTP, lịch sử. |
| 1 | 0,5: ERD có entity, thuộc tính, khóa, quan hệ hợp lý | Đạt | [ERD năm service](../diagrams/ERD.md), đối chiếu models/migrations; phân biệt FK nội bộ với ID tham chiếu xuyên service. |
| 2. Microservices — 1,5 | 0,5: Architecture Diagram rõ ràng | Đạt | [Architecture](../diagrams/ARCHITECTURE.md), [SVG](../diagrams/rendered/architecture-1.svg). |
| 2 | 0,5: Phân rã service và trách nhiệm hợp lý | Đạt | [Báo cáo mục 2](REPORT.md): Auth, Wallet, Tuition, Payment, Notification; worker là tiến trình của service sở hữu. |
| 2 | 0,5: Giao tiếp, database, external service; giải thích kiến trúc | Đạt | REST/JWT/service key, năm DB/role riêng, Saga/outbox, SMTP Mailpit trong [Architecture](../diagrams/ARCHITECTURE.md), [Sequence](../diagrams/SEQUENCE.md), [Compose](../../compose.yaml). |
| 3. REST API — 1,0 | 0,5: Đủ API chính, URI và HTTP method hợp lý | Đạt | [Contract](../api/CONTRACT.md): tám API công khai và reservation/message API nội bộ; năm OpenAPI JSON cùng thư mục. |
| 3 | 0,5: Request/response, status, validation, error handling | Đạt | OpenAPI [Auth](../api/auth.openapi.json), [Wallet](../api/wallet.openapi.json), [Tuition](../api/tuition.openapi.json), [Payment](../api/payment.openapi.json), [Notification](../api/notification.openapi.json); lỗi `code/message/requestId`, DTO từ chối trường ngoài hợp đồng. |
| 4. Database & Persistence — 1,0 | 0,5: Database phù hợp thiết kế, đủ dữ liệu | Đạt | PostgreSQL 18, volume bền vững trong [Compose](../../compose.yaml); [khởi tạo năm DB/user](../../infra/db/init.sh); migration/seed của từng service. |
| 4 | 0,5: Constraints, validation, seed và persistence đúng | Đạt | [Wallet migration](../../services/wallet/migrations/versions/0001_initial.py): tiền không âm, reserved ≤ balance, debit duy nhất; [Tuition migration](../../services/tuition/migrations/versions/0001_initial.py): invoice/student/state; [Payment migration](../../services/payment/migrations/versions/0001_initial.py): OTP/idempotency/outbox; seed lặp không reset giao dịch. |
| 5. Chức năng & Payment — 2,0 | 0,5: Đăng nhập, tài khoản, tra học phí | Đạt | [Auth](../../services/auth/app.py), [Wallet](../../services/wallet/app.py), [Tuition](../../services/tuition/app.py); kiểm tra đúng/sai login, thiếu JWT, không có MSSV/khoản thu/đã trả. |
| 5 | 0,5: Khởi tạo/thực hiện giao dịch, kiểm tra số dư/học phí | Đạt | [Payment API](../../services/payment/app.py): backend xác định payer/email/amount, bắt buộc điều khoản và UNPAID; Wallet/Tuition kiểm tra lại khi reserve. |
| 5 | 0,5: OTP gắn giao dịch, có hạn, dùng một lần, gửi email | Đạt trong phạm vi Mailpit | OTP sáu số, tối đa năm phút/năm lần sai, HMAC và unique ACTIVE; consume nguyên tử; email OTP mã hóa qua outbox/Notification. [Biên bản kiểm chứng](VERIFICATION.md). |
| 5 | 0,5: Thành công cập nhật số dư, PAID, lịch sử, email | Đạt | [Saga/outbox](../../services/payment/worker.py), [Notification SMTP](../../services/notification/worker.py): capture → PAID → SUCCEEDED + outbox; lịch sử lọc theo chủ tài khoản. Ca web live và kiểm tra email đúng Payment ở mục 2. |
| 6. Transaction & Concurrency — 1,5 | 0,5: Nhất quán khi cập nhật dữ liệu liên quan | Cần xác minh thêm nhánh recovery thành công; ca timeout mới hủy sạch | [Sequence](../diagrams/SEQUENCE.md), checkpoint bền vững, ABORTING trước quyết định/forward recovery sau COMMITTING; kiểm chứng crash/lost response lịch sử được tách riêng ở [VERIFICATION](VERIFICATION.md). Ca mới và đối soát ở mục 2. |
| 6 | 0,5: Nhiều giao dịch cùng ví không vượt số dư | Đạt | Test PostgreSQL/REST thật: ví 10 triệu tranh hai khoản 6 triệu → một thành công, một thất bại sạch, còn 4 triệu, reserved 0 và một debit. |
| 6 | 0,5: Nhiều tài khoản trả một khoản chỉ thành công một lần | Đạt | Test PostgreSQL/REST thật: một SUCCEEDED/một FAILED, invoice PAID một lần; người thắng còn 4 triệu, người thua giữ 10 triệu, tổng một debit. |
| 7. UI & Integration — 0,5 | Toàn luồng đăng nhập → tra cứu → thanh toán → OTP → kết quả/lịch sử, tích hợp API thật | Đạt; live web mới đạt, vẫn ghi timeout gateway riêng | [Controller gọi API](../../frontend/src/main.tsx), [các màn hình](../../frontend/src/pages.tsx), [OTP input](../../frontend/src/OtpCodeInput.tsx), ảnh chọn trong [VERIFICATION](VERIFICATION.md). 44 ca UI mock không thay bằng chứng live. |
| 8. Documentation / Deploy / Demo — 1,5 | 0,5: README cài đặt, cấu hình, khởi chạy | Đạt | [README](../../README.md), [.env.example](../../.env.example), [setup.py](../../setup.py). |
| 8 | 0,5: Triển khai và tích hợp thành hệ hoàn chỉnh | Có stack chạy; cần lưu ý timeout gateway | [Compose](../../compose.yaml), Dockerfiles/Nginx; demo và test đều có API/DB healthy. Một kiểm tra gateway có timeout được ghi ở mục 2, không bỏ khỏi kết quả. |
| 8 | 0,5: Demo thành công và giải thích kiến trúc/API/transaction/concurrency | Đủ tài liệu và bằng chứng demo đã chọn; nhóm cần trình bày trực tiếp | [DEMO](../demo/DEMO.md), [REPORT](REPORT.md), [VERIFICATION](VERIFICATION.md). Demo riêng bằng cùng cấu hình trong production; phân biệt thao tác minh họa với kiểm thử đồng thời tự động. |

## 2. Kiểm chứng mới trong lần rà soát này

Các lệnh dưới đây đã thực chạy ngày 16/11/2026. Lệnh test được ghi để truy nguyên kết quả từ workspace đầy đủ; chương trình nộp được chạy bằng README trong `production`.

| Kiểm tra | Kết quả thực tế | Phạm vi / giới hạn |
|---|---|---|
| `.venv/Scripts/python.exe tools/run_checks.py` (cwd non-prod) | **50 passed**, ba nhóm đều exit 0 | Core 5 (18,29s); financial 32 (64,29s); payment 13 (11,61s). PostgreSQL thật cho DB; các HTTP dependency giả lập vẫn được phân biệt với live. |
| Playwright `frontend.spec.ts navigation.spec.ts login.spec.ts otp.spec.ts`, baseURL `http://127.0.0.1:18080` | **44 passed, exit 0**, 2,2 phút | Chromium trên Nginx hiện có; mock API để kiểm tra UI, trạng thái, retry, điều hướng và OTP. |
| Playwright `live.spec.ts --workers=1 --trace=off`, `LIVE_STACK=1`, sau reset riêng dữ liệu test | **1 passed, exit 0**, 30,4s (test 16,1s) | Không mock: login → tổng quan → tra cứu → tạo Payment → OTP nhận Mailpit → SUCCEEDED → tổng quan/lịch sử. REST xác nhận balance/available 4 triệu, reserved 0, invoice PAID 6 triệu và đúng Payment trong lịch sử. |
| Đối chiếu email kết quả của đúng Payment sau live | **Assert đạt, exit 0** | Đọc Payment SUCCEEDED mới nhất ở DB test; tìm thư Mailpit có subject thành công, đúng Payment ID và 6.000.000 VND trong nội dung. Không in/lưu OTP hoặc JWT. |
| pytest `tests/integration/system tests/integration/notification --tb=short -q` | **8 passed, 1 failed, exit 1**, 215,98s | Hai ca concurrency, nghiệp vụ/quyền/idempotency và Notification đạt. Ca gateway timeout khi GET `/api/v1/payments` **trước** bước thay mới container. |
| pytest chạy riêng `test_gateway_routes_current_services_after_container_replacement` | **1 passed, exit 0**, 79,17s | Cả kiểm tra ban đầu và sau khi recreate năm API đều đạt. Không sửa code hoặc tăng timeout; lượt này không xóa kết quả lỗi của suite trước. |
| Docker Compose `ps` cho demo và test | **Exit 0** | API/DB healthy, hai worker chạy; runtime chỉ publish web loopback 8080, stack test có cổng riêng. |
| Compose `config --quiet` với `WEB_PORT=18081`, project `soa-midterm-review-wallet` và `soa-midterm-review-invoice` | **Cả hai exit 0** | Kiểm tra cấu hình demo độc lập; không tạo hai project này trong lượt audit. |
| SVG UML mới | XML/quan hệ đạt; Chromium render exit 0, đã xem ảnh | Hai actor, chín use case, 12 quan hệ khớp `.puml`; chữ/mũi tên đọc được, không phụ thuộc tài nguyên ngoài. |
| Kiểm tra tài liệu bộ nộp | **Exit 0** | 10 file Markdown, 133 liên kết cục bộ; 0 liên kết hỏng, 0 liên kết ra ngoài production. 11 SVG parse XML, năm OpenAPI parse JSON. |
| pytest `tests/recovery/system --tb=short -q` | **Chưa kết luận lượt chạy** | Phiên bị ngắt trước khi thu được tổng kết/traceback/exit code; có ký hiệu F trong output từng phần. Không tính lượt này là đạt, không suy đoán lỗi source từ output thiếu. |
| pytest chạy riêng recovery `[tuition-RESERVED]`, có JUnit | **1 failed, exit 1**, 83,70s | Test kỳ vọng SUCCEEDED sau mất response/restart, thực tế FAILED. Đọc DB và worker log xác định `PREPARE_TIMEOUT`, saga ABORTING checkpoint 2, hai ví vẫn 10 triệu/reserved 0, debit của Payment = 0, Tuition reservation CANCELLED, invoice UNPAID. |

Lượt Playwright ban đầu trong sandbox lỗi IPC `EPIPE` trước khi các ca được thực thi; lượt chạy ngoài sandbox đạt 44/44. Lượt backend đầu trong sandbox không tiến qua khởi chạy test và đã dừng; lượt thực thi lại đạt ba nhóm. Không tính các lượt bị chặn này thành test ứng dụng đạt hoặc lỗi nghiệp vụ.

## 3. Điểm cần biết trước khi nộp

- **Timeout gateway cần được giữ trong kết luận.** Log Nginx của lượt lỗi có login/me/wallet/tuition trả 200, riêng `/api/v1/payments` kết thúc 499 sau khi client hết thời gian chờ. Chưa đủ bằng chứng để quy nguyên nhân cho DNS, database hoặc hiệu năng máy; chưa sửa source runtime theo suy đoán.
- **Recovery chưa đạt toàn bộ kiểm chứng mới.** Ca mất response sau Tuition reserve kết thúc PREPARE_TIMEOUT trước COMMITTING và hủy sạch, phù hợp quy tắc deadline 30 giây; test yêu cầu phục hồi thành SUCCEEDED nên vẫn thất bại. Cần làm rõ thời gian tái khởi động/thực thi của test trước khi kết luận có lỗi nhánh recovery thành công. Không tăng deadline nghiệp vụ hoặc ghi test đạt để che kết quả này.
- **Email chỉ tới Mailpit.** Ứng dụng dùng SMTP thật tới hộp thư bắt thư cục bộ; chưa chứng minh thư tới Gmail/Outlook. Nếu giảng viên yêu cầu hộp thư Internet, cần cấu hình và kiểm chứng thêm.
- Một assertion tích hợp cũ chỉ kiểm tra có bất kỳ job email kết quả `SENT`, chưa lọc đúng Payment đang chạy. Lượt audit này bổ sung đối chiếu thư thật tại Mailpit theo đúng Payment SUCCEEDED và số tiền sau ca web live; assertion đạt. Hạn chế của assertion cũ vẫn được ghi để không suy rộng bằng chứng đó.
- Saga có khoảng thời gian PROCESSING khi phục hồi. SMTP có thể gửi trùng sau crash; không tuyên bố exactly-once email hoặc ACID xuyên năm database.
- Chưa chấm phần thuyết trình trực tiếp, thiết bị thật, trình duyệt khác hoặc triển khai ngân hàng công khai. Không đưa `.env`, private key hoặc dữ liệu thật vào bài nộp.

## 4. Thứ tự mở bộ nộp khi chấm

1. [README](../../README.md): khởi chạy và đăng nhập.
2. [Use Case](../diagrams/USE_CASE.md), [ERD](../diagrams/ERD.md), [Architecture](../diagrams/ARCHITECTURE.md), [Sequence](../diagrams/SEQUENCE.md).
3. [API Contract](../api/CONTRACT.md) và năm OpenAPI JSON.
4. [Báo cáo thiết kế](REPORT.md), [kết quả kiểm chứng](VERIFICATION.md), bảng đối chiếu này.
5. [Demo](../demo/DEMO.md): luồng chính, trả hộ, nhánh lỗi, đồng thời và phục hồi.
