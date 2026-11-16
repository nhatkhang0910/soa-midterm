# Biên bản kiểm chứng và bàn giao

Ngày **16/11/2026**, múi giờ Asia/Saigon. Phạm vi: toàn bộ T00–T14, bản mô phỏng cục bộ; email giả qua Mailpit theo yêu cầu cuối của người dùng.

## Kết quả

**80 ca kiểm tra riêng biệt đã đạt**, qua các bộ lệnh dưới đây; không phải một lần chạy chung tất cả test trong cùng process.

| Bộ kiểm tra | Kết quả đã đọc | Phạm vi |
|---|---:|---|
| Backend service suite | **50 ca đạt** qua ba nhóm, mỗi nhóm exit 0 | Common/Auth/Notification 5; Wallet/Tuition 32; Payment/OTP/Saga/outbox 13. PostgreSQL thật; dependency HTTP giả lập được ghi rõ. |
| REST xuyên service và Mailpit | **9 ca đạt** qua hai lệnh, exit 0 | Gateway phục hồi sau recreate service; thanh toán/lịch sử, quyền, idempotency; hai race tài chính; email retry/restart/dedup/OTP hết hạn khi đang chờ. |
| Phục hồi và cách ly DB | **8 ca đạt** qua nhóm 5 + 3, exit 0 | Mất response sau bốn commit REST; restart trước capture và sau SUCCEEDED/outbox; hết deadline chuẩn bị; role không kết nối chéo 20 cặp DB. |
| Playwright UI với API giả lập | **12 passed**, exit 0 | Điều khoản/OTP/lookup, retry, resume, phân trang, logout, mobile; ba regression phản hồi trễ. Chạy trên web Nginx build cuối. |
| Playwright với backend thật | **1 passed**, exit 0 | Chromium trả học phí bằng OTP nhận từ Mailpit, kết quả thành công và số dư đúng; không mock API. |

Lệnh tái lập từ `non-prod`:

```powershell
.venv/Scripts/python.exe tools/run_checks.py
.venv/Scripts/python.exe -m pytest tests/integration/system tests/integration/notification --tb=short -q
.venv/Scripts/python.exe -m pytest tests/recovery/system --tb=short -q
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:18080'
npx playwright test tests/e2e/frontend.spec.ts --config playwright.config.ts --reporter=list
.venv/Scripts/python.exe tools/reset_test_data.py
$env:LIVE_STACK='1'
npx playwright test tests/e2e/live.spec.ts --config playwright.config.ts --reporter=list
```

Đây là lệnh truy nguyên của bộ kiểm thử phát triển trong workspace đầy đủ. Chạy tuần tự; live tests reset/dừng worker trong **stack test riêng**, không dùng database demo. Không chạy bare pytest gom các service dùng engine/metadata khác nhau. Kết quả chọn lọc ở tài liệu này đủ đọc trong bộ nộp; để chạy ứng dụng và trình diễn từ riêng `production`, dùng [README](../../README.md) và [DEMO](../demo/DEMO.md).

## Các bất biến đã kiểm tra

- Ví 10 triệu tranh hai học phí 6 triệu: một giao dịch thành công, một thất bại sạch; balance/available còn 4 triệu, reserved 0, đúng một debit.
- Hai tài khoản cùng một học phí: một người bị ghi nợ; bên thua giữ nguyên tiền, invoice PAID đúng người thắng.
- Retry/capture đồng thời cùng Payment không trừ tiền lần hai; payload khác cùng ID bị từ chối; tombstone chặn reserve tới muộn.
- OTP sáu chữ số, HMAC/unique ACTIVE, collision exhaustion rollback, năm lần sai, expiry, consume đồng thời và ownership được kiểm tra. JWT sai audience/hết hạn bị từ chối.
- Crash sau reserve/capture/PAID, hoặc sau quyết định COMMITTING và sau SUCCEEDED, phục hồi từ PostgreSQL tới trạng thái cuối nhất quán. Hết prepare deadline giải phóng cả hai bên; COMMITTING tiếp tục retry.
- Outbox chỉ xóa payload sau ACK bền vững/hết hạn; Notification dedup sau purge, retry SMTP lỗi, khôi phục sau restart; OTP đã hết hạn trong hàng đợi không được gửi.

## Build, giao diện và tài liệu

- Docker build cả demo/test **exit 0**; frontend TypeScript/Vite build **exit 0**. Bản demo `docker compose up -d --no-build --wait` **exit 0** và đang chạy tại [localhost:8080](http://localhost:8080).
- Kiểm tra web/auth/wallet/Mailpit qua Nginx đạt; `/internal` trả 404. Bản demo giữ nguyên số dư seed **10 triệu/người**; kiểm thử giao dịch dùng volume test riêng.
- Xuất **5 OpenAPI JSON** từ source cuối, có request/response/error schemas và bearer auth. [Hợp đồng API](../api/CONTRACT.md) mô tả URI, HTTP method, dữ liệu, status và xác thực nội bộ.
- **10 sơ đồ Mermaid** đã render và kiểm tra cú pháp bằng Chromium; bản SVG trong `../diagrams/rendered`. Lỗi dấu chấm phẩy trong Sequence đã được sửa rồi render lại thành công. Use Case còn có nguồn UML PlantUML.
- Ảnh desktop/mobile luồng thật đã được xem: không tràn ngang, tiền và trạng thái hiển thị đúng. Bản chọn: [desktop](images/live-success-desktop.png), [mobile](images/live-success-mobile.png).

## Review độc lập

| Phạm vi | Verdict cuối | Finding đã xử lý |
|---|---|---|
| Hợp đồng API/OTP/Saga | PASS | Fingerprint email sống sau purge; Payment kết thúc khi OTP hết hạn/khóa. |
| Wallet/Tuition | PASS | Credential Unicode trả 403; bổ sung overlap cùng paymentId và kiểm tra hai session chờ khóa. |
| Bảo mật/Auth/OTP/Saga/Notification/hạ tầng | PASS | Bổ sung OTP hết hạn khi QUEUED; env tối thiểu; chứa lỗi ngoài dự kiến an toàn; gateway DNS phục hồi sau recreate. |
| UI/tài liệu/config | PASS | Khóa MSSV trong lookup; bỏ response lịch sử lỗi thời; sửa tên `.env` trong demo. |

Reviewer khác tác giả. Astra hết hạn mức ở gate ban đầu; dùng **Sol xhigh** thay thế đúng quy tắc dự án và đã thông báo. Không còn finding P1/P2 chưa xử lý trong các scope review này.

Bản chọn cho chấm điểm gồm các bảng kết quả, bất biến, kết luận review ở trên và ảnh trong `images/`. Log backend, REST/recovery và ghi chú review thô được lưu ở workspace phát triển, không phải thành phần bắt buộc của bộ nộp. Số ca và phạm vi của từng lệnh được giữ riêng, không coi mock HTTP hoặc ảnh giao diện là bằng chứng concurrency xuyên service.

## Giới hạn còn lại

Đây là mô phỏng học tập dùng HTTP loopback và dữ liệu giả, chưa dùng cho ngân hàng hoặc triển khai công khai. Không kiểm tra SMTP thật vì người dùng chọn Mailpit. Mailpit là hộp thư chung trên máy; SMTP có thể gửi trùng khi crash sau gửi trước ghi SENT. Saga có trạng thái PROCESSING trong thời gian phục hồi và cần đối soát khi service/dữ liệu bị lỗi lâu dài.

Có một `StarletteDeprecationWarning` trong unit TestClient và cảnh báo môi trường màu của Node; không có test thất bại. Runner có thể để lại schema test nếu bị kill cưỡng bức. Không tạo Git, commit/push, cloud, broker, đăng ký, nạp/chuyển tiền hoặc admin ngoài yêu cầu.

## Bổ sung T15–T18 — trang tổng quan và giao diện

Ngày 16/11/2026, hoàn thiện trang tổng quan sau đăng nhập tại `/`, đăng nhập `/login`, học phí `/tuition` và lịch sử `/tuition?view=history&page=N`. URL lịch sử cũ được chuyển sang địa chỉ mới. UI navy/trắng/teal dùng UI-UX Pro Max và Impeccable; không thêm dependency runtime, thay API hoặc sửa backend.

- **27 ca frontend đạt**, exit 0, trên Nginx build cuối: đủ 12 ca cũ và 15 ca điều hướng/phục hồi. Có hồi quy RED/GREEN cho lỗi mở chi tiết, khôi phục Payment, lịch sử sau polling và không chồng request qua chuyển trạng thái.
- **1 ca live Mailpit đạt**, exit 0: đăng nhập → tổng quan → học phí → OTP → thành công → tổng quan. REST xác nhận số dư/khả dụng 4 triệu, reserved 0, invoice PAID 6 triệu và đúng một Payment tương ứng trong danh sách gần đây. Test dùng database/volume riêng; không reset dữ liệu demo.
- **6 ảnh và 32 kiểm tra bố cục đạt** tại 320/390/768/1440px, gồm tên/email dài, số dư lớn và ô tra cứu nằm trong màn hình đầu 390×844. Detector Impeccable không có finding. Review độc lập UI Sol high và trạng thái phiên Astra xhigh đã đóng các finding trong phạm vi được giao.
- Docker build web cuối và cập nhật riêng container web demo **exit 0**. Demo [localhost:8080](http://localhost:8080) và test dùng cùng asset cuối; các đường dẫn SPA và chặn `/internal` được kiểm tra bằng HTTP, không phát sinh giao dịch demo.

Ảnh được chọn: [tổng quan desktop](images/dashboard-home-desktop.png), [đăng nhập desktop](images/dashboard-login-desktop.png), [học phí mobile](images/dashboard-tuition-mobile.png). Đây là ảnh với API fixture; bằng chứng tài chính thật là ca live riêng.

Bộ backend concurrency/recovery lịch sử phía trên không được chạy lại trong đợt thay giao diện này. Chỉ kiểm tra Chromium; chưa kiểm tra thiết bị thật, trình đọc màn hình hoặc zoom. JWT vẫn chỉ trong bộ nhớ nên tải lại trang cần đăng nhập lại. Các kết quả và ảnh được chọn ở mục này là bằng chứng bàn giao cho T15–T18; log chi tiết được lưu riêng tại workspace phát triển.

## Bổ sung T19 — login theo video tham khảo

Login chuyển sang form trắng giữa màn hình, nút navy và bóng đổ mềm theo video người dùng cung cấp. Background nguyên bản kết hợp khuôn viên trường, sách/mũ tốt nghiệp, thẻ ngân hàng trống và phong bì học phí theo điều chỉnh cuối của người dùng. Ảnh minh họa hư cấu, không đại diện một trường/ngân hàng thực tế; WebP local khoảng 177 KB, không tải tài nguyên ảnh bên ngoài.

Build TypeScript/Vite, **35 ca UI** trên Nginx cuối, **hai ảnh/năm viewport**, detector Impeccable và review độc lập Sol high đều đạt. Giữ nguyên luồng đăng nhập/Auth/API và dependency. Bản web demo đã được cập nhật riêng; dữ liệu demo không reset. Ảnh chọn: [desktop](images/login-reference-desktop.png), [mobile](images/login-reference-mobile.png).

Bằng chứng chọn T19 là kết quả build/35 ca UI, kết luận review và hai ảnh ở mục này. Chỉ kiểm tra Chromium; màn hình thấp cuộn dọc bình thường. Không chạy lại backend/live payment suites vì thay đổi chỉ ở giao diện login.

## Bổ sung T20 — nhập OTP theo video tham khảo

OTP chuyển thành sáu ô chia nhóm 3+3 theo video, giữ một trường nhập có nhãn để hỗ trợ dán mã, số 0 đầu và bàn phím. Ô đang nhập có focus navy, lỗi có chữ/màu, chờ xác thực khóa nhập/nút. Người dùng vẫn chọn **Xác nhận thanh toán** hoặc nhấn Enter; hạn mã, số lần sai và kết quả lấy từ server. Biên nhận từ server, controller và API không đổi.

Build TypeScript/Vite, **44 ca UI** (35 cũ + 9 OTP), **một ca live Mailpit** và review độc lập Astra xhigh đạt. Ba finding về focus khi thử lại, con trỏ ở tương phản cao và trường nhập hiện đè lúc bị khóa đã sửa và kiểm tra lại. Một lượt chụp có bảy ảnh/bảy kiểm tra qua năm kích thước, lỗi và reduced motion; không tràn ngang, tương phản chữ được đo tối thiểu 5.81:1. Detector Impeccable trả `[]` trước các sửa hành vi/selector; bản cuối được review thủ công. Demo web đã cập nhật riêng, không reset dữ liệu demo.

Ảnh chọn dùng API fixture: [desktop](images/otp-reference-desktop.png), [mobile](images/otp-reference-mobile.png). Ca live riêng xác nhận học phí PAID, số dư còn 4.000.000 VND, đang giữ 0 và lịch sử đúng. Kết quả 44 ca UI/một ca live và kết luận review ở mục này là bằng chứng chọn T20. Chưa kiểm tra thiết bị thật, trình đọc màn hình hoặc trình duyệt khác; không chạy lại toàn bộ backend concurrency/recovery trong đợt T20. Rà soát theo bảng chấm mới được ghi riêng ở [RUBRIC_AUDIT](RUBRIC_AUDIT.md).

## Rà soát theo tiêu chí chấm — trạng thái mới nhất

Bộ nộp đã bổ sung [bảng đối chiếu đủ từng phần điểm](RUBRIC_AUDIT.md), ảnh Use Case ký pháp UML và hướng dẫn demo bằng project Compose riêng từ chính `production`. README, API, sơ đồ, báo cáo và demo không còn liên kết file bắt buộc ra ngoài bộ nộp.

Lượt rà soát mới đạt **50 ca backend, 44 ca UI mock, một ca web live Mailpit và hai ca concurrency REST**. Ca web live mới exit 0, 30,4 giây; REST xác nhận số dư còn 4 triệu/reserved 0, invoice PAID và lịch sử đúng. Suite REST/Notification có 8 đạt/1 lỗi timeout gateway; chạy riêng lại ca gateway đạt. Ca recovery sau Tuition reserve mới chạy lại **chưa đạt**: kỳ vọng SUCCEEDED, thực tế FAILED/PREPARE_TIMEOUT; đã xác nhận không ghi nợ, hai ví giữ nguyên, reservation hủy và invoice UNPAID. Bằng chứng lịch sử phía trên không thay kết quả mới này. Xem lệnh, phạm vi, giới hạn và kết luận hiện hành trong bảng đối chiếu; chưa tuyên bố đạt trọn bộ tiêu chí.
