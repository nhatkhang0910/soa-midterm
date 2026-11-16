# Kịch bản demo iBanking

Email **chỉ giả lập qua Mailpit**. Không cần tài khoản email thật hoặc SMTP Internet. Hướng dẫn setup/secrets và lệnh chạy đầy đủ ở [README](../../README.md); đặc tả ở [Contract](../api/CONTRACT.md). Đây là kịch bản với kết quả mong đợi, không phải tuyên bố đã chạy nghiệm thu.

## 1. Chuẩn bị

Chạy runtime theo README từ thư mục `production`:

```powershell
docker compose --env-file .env -f compose.yaml up --build -d
docker compose --env-file .env -f compose.yaml ps
```

Mở [web demo](http://localhost:8080/) và [Mailpit demo](http://localhost:8080/mail/). API tự migrate/seed khi khởi động. Worker Payment và Notification phải đang chạy; chờ API healthy. Không quay màn hình `.env`, secret, JWT, nội dung log nhạy cảm. OTP chỉ đọc trong hộp thư demo, không sao chép vào báo cáo.

| Dữ liệu seed mới | Giá trị |
|---|---|
| Người nộp An | username `an`, mật khẩu `Demo@123456`, Nguyễn Văn An. |
| Người nộp Bình | username `binh`, mật khẩu `Demo@123456`, Trần Thanh Bình. |
| Ví | Mỗi người 10.000.000 VND, reserved 0. |
| `52200001` | Nguyễn Văn An, UNPAID, 6.000.000 VND. |
| `52200002` | Trần Thanh Bình, UNPAID, 6.000.000 VND. |
| `52200003` | Lê Minh Châu, PAID. |
| `52200004` | Phạm Ngọc Dung, không có khoản thu. |
| `99999999` | MSSV không tồn tại. |

Nếu cấu hình DEMO_PASSWORD đã đổi, dùng mật khẩu local tương ứng. Seed lặp an toàn không reset dữ liệu đã thay đổi: một lần thanh toán sẽ ảnh hưởng các ca sau. Mỗi ca độc lập cần database mới; dùng tên project Compose mới theo hướng dẫn dưới đây, giữ dữ liệu demo chính.

### Môi trường trình diễn riêng, chỉ dùng production

Sau khi setup theo README, mở một PowerShell tại `production`. Dùng cùng mã nguồn/cấu hình/secrets cục bộ nhưng tên project và cổng web riêng:

```powershell
$env:WEB_PORT='18081'
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-wallet up -d --build --wait
```

Web riêng ở [localhost:18081](http://localhost:18081/), Mailpit riêng ở [18081/mail/](http://localhost:18081/mail/). Tên project tạo network và volume PostgreSQL riêng; không nối vào database của project demo chính. Các lệnh sau phải giữ đúng `-p`. Chỉ dùng dữ liệu giả; không trình chiếu secret/OTP trong báo cáo.

Sau ca một ví/hai khoản, dừng project đó để nhường cổng rồi tạo project mới cho ca hai ví/một khoản:

```powershell
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-wallet stop
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice up -d --build --wait
```

Tên project đã dùng sẽ giữ dữ liệu cũ; chọn tên mới nếu cần diễn lại trên seed mới. Sau trình diễn, dừng đúng project bằng `docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice stop`, rồi `Remove-Item Env:WEB_PORT`. Không cần xóa volume hoặc thư mục ngoài `production`.

## 2. Demo chính — khoảng 5 phút

1. Tại `/login`, nhập `an` với mật khẩu sai: thấy thông báo đăng nhập lỗi. Đăng nhập bằng `Demo@123456`: vào trang tổng quan `/` có tên người nộp, số dư khả dụng và số dư 10.000.000 VND, đang giữ 0 trên dữ liệu mới. Danh sách hiển thị tối đa năm giao dịch mới nhất thực tế; ban đầu có thể rỗng.
2. Chọn **Thanh toán học phí** để mở `/tuition`. Màn hình có ba nhóm: thông tin người nộp chỉ đọc; thông tin học phí theo MSSV; điều khoản/xác nhận. Tra `52200001`, thấy tên và 6.000.000 VND. Khi chưa tích điều khoản chưa được tạo thanh toán.
3. Tích **Tôi đồng ý**, chọn **Tiếp tục xác thực**. Giao dịch ở trạng thái chờ OTP; chưa trừ tiền. Chỉ Payment ID/thời hạn được trả API, không có OTP trong response.
4. Chuyển sang Mailpit, chọn thư OTP đúng người nhận và Payment ID. Nhập sai một mã khác mã hiện tại: lỗi OTP, còn có thể thử lại. Nhập hoặc dán mã thật trong 5 phút vào sáu ô số; số 0 đầu được giữ nguyên. Chọn **Xác nhận thanh toán** hoặc nhấn Enter để gửi; nhập đủ sáu số không tự xác nhận. Khi chờ phản hồi, vùng nhập và nút xác nhận tạm khóa.
5. Màn hình chuyển **Đang xử lý**, tự cập nhật mỗi hai giây. Chờ **Thanh toán thành công** rồi về trang tổng quan: số dư và khả dụng còn 4.000.000 VND, đang giữ 0; giao dịch mới nhất có cùng Payment ID, số tiền và trạng thái thành công. Vào **Thanh toán học phí**, chọn **Thanh toán khoản khác** để mở lại ô tra cứu, tra `52200001` là PAID; xem **Lịch sử giao dịch** tại `/tuition?view=history&page=1` có cùng bản ghi.
6. Trong Mailpit có thư thanh toán thành công gửi người nộp. Email kết quả có thể tới sau khi UI thành công; chậm email không đảo ngược giao dịch.

Khi thuyết trình, giải thích: UI chỉ báo thành công sau Wallet capture và Tuition PAID, không báo thành công ngay khi OTP đúng. Email lưu qua outbox/job và có thể bị gửi trùng sau crash; hiệu ứng tài chính vẫn idempotent.

Điều hướng dùng liên kết, hỗ trợ nút Quay lại của trình duyệt; URL lịch sử cũ `/?view=history` chuyển tới `/tuition?view=history&page=1`. Trang tổng quan yêu cầu đăng nhập. JWT chỉ ở bộ nhớ, nên tải lại trang phải đăng nhập lại; Payment ID đang chờ được lưu riêng theo người dùng và có thể mở từ **Tiếp tục giao dịch** trên trang tổng quan. Có thể thử đi về trang chủ khi chờ OTP, mở một biên nhận cũ rồi tiếp tục Payment hiện tại: việc xem biên nhận không được làm mất giao dịch đang chờ.

## 3. Trả hộ và các nhánh lỗi

| Ca | Thao tác | Kết quả mong đợi |
|---|---|---|
| Trả hộ | Trên dữ liệu mới, `an` tra `52200002` rồi thanh toán. | Người nộp An, sinh viên Bình; trừ ví An, OTP/kết quả tới email An. |
| Khoản đã trả | Tra `52200003`. | Hiển thị đã thanh toán, không cho tiếp tục. |
| Không có khoản | Tra `52200004`. | Hiển thị không có khoản thu, không tạo Payment. |
| Không có sinh viên | Tra `99999999`. | Báo không tìm thấy sinh viên. |
| Thiếu tiền | Sau ca An trả `52200001`, tra `52200002` còn UNPAID. | Số dư 4 triệu không đủ khoản 6 triệu; bị chặn. |
| OTP hết hạn | Tạo Payment mới ở dữ liệu phù hợp, chờ hơn 5 phút rồi xác nhận. | EXPIRED, không trừ tiền; phải tạo giao dịch mới, không có resend v1. |
| OTP khóa | Tạo Payment mới, dùng một mã chắc chắn khác thư hiện tại, nhập sai 5 lần. | OTP_LOCKED/FAILED; không trừ tiền. |
| Phân quyền | Dùng API test có JWT Bình truy cập Payment An. | 403; lịch sử Bình không có Payment An. Không dán JWT vào tài liệu. |

Ca trả hộ là một kịch bản độc lập với demo chính: trên cùng dữ liệu, An chỉ đủ tiền trả một khoản 6 triệu. Dùng project demo riêng mới hoặc chọn Bình làm người nộp khi cần diễn tiếp.

## 4. Hai ca đồng thời

Các ca tự động PostgreSQL thật và kết quả đối soát đã chọn ở [biên bản kiểm chứng](../report/VERIFICATION.md) và [bảng tiêu chí](../report/RUBRIC_AUDIT.md). Thao tác hai trình duyệt dưới đây phục vụ trình diễn; không thay thế bằng chứng test có barrier/kiểm tra DB. Dùng project demo riêng mới ở mục 1 cho từng ca.

**Một ví, hai khoản:** dùng hai phiên trình duyệt `an` trên dữ liệu test mới; mỗi phiên tạo Payment cho một MSSV `52200001`/`52200002` trước khi xác nhận. Mỗi Payment có OTP riêng. Xác nhận gần đồng thời. Chờ cả hai kết thúc: một SUCCEEDED, một FAILED; ví An còn 4 triệu/reserved 0; một debit; chỉ invoice thắng PAID.

**Hai ví, một khoản:** dữ liệu test mới; phiên An và phiên Bình cùng tạo Payment cho `52200001`, rồi xác nhận. Một người thắng; invoice PAID một lần; chỉ ví người thắng giảm 6 triệu; người thua đủ 10 triệu/reserved 0. Chủ mỗi tài khoản chỉ thấy lịch sử của mình.

Chọn Payment ID làm khóa đối soát. Nếu một Payment còn PROCESSING, chưa kết luận race đã đạt; phải chờ worker phục hồi rồi kiểm tra các invariant cùng lúc.

## 5. Phục hồi, timeout và email

1. **Restart thông thường:** trong project demo riêng mới, nhận email OTP rồi dừng `payment-worker`. Xác nhận OTP trên web khi worker đang dừng để Payment chuyển PROCESSING; khởi động lại worker ngay, trong 30 giây kể từ confirm, rồi chờ hoàn tất. Nếu quá prepare deadline 30 giây trước COMMITTING, kết quả hợp lệ là FAILED sau khi dọn reservation. Restart này minh họa công việc bền vững, chưa chứng minh crash tại mọi ranh giới.
2. **Mất response sau commit:** trình bày [kết quả recovery qua service thật](../report/VERIFICATION.md) và [Sequence](../diagrams/SEQUENCE.md): mất ACK Wallet/Tuition rồi restart worker vẫn có debit duy nhất và invoice PAID; lỗi sau COMMITTING không refund/mở invoice.
3. **Hủy trước reserve:** trình bày kết quả tombstone trong [biên bản kiểm chứng](../report/VERIFICATION.md): cancel đến trước reserve phải chặn reserve tới muộn. Phân biệt HTTP test double với test boundary thật theo bảng kết quả.
4. **Notification restart/email lỗi:** tạo Payment và nhận OTP trước, rồi dừng `notification-worker`; xác nhận OTP để hoàn tất Payment. Tài chính vẫn SUCCEEDED, job email kết quả chờ; khởi động worker thì thư tới Mailpit. Để minh họa OTP hết hạn trong hàng đợi, dùng một ca riêng: dừng worker trước khi tạo Payment, chờ quá năm phút rồi khởi động lại; thư OTP quá hạn bị bỏ và payload được xóa, cần tạo Payment mới.

Ví dụ restart chỉ trên project demo riêng đang dùng, cwd `production` (thay tên project nếu khác):

```powershell
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice stop payment-worker
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice start payment-worker
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice stop notification-worker
docker compose --env-file .env -f compose.yaml -p soa-midterm-review-invoice start notification-worker
```

Chạy mỗi cặp stop/start đúng thời điểm trong ca tương ứng, không paste cả khối rồi gọi đó là kiểm thử phục hồi. Không dùng `down -v` để dọn runtime. Nếu cần môi trường mới, chọn tên project Compose mới theo mục 1.

## 6. Checklist trình bày và bằng chứng

- Mở [Use Case](../diagrams/USE_CASE.md), [ERD](../diagrams/ERD.md), [Architecture](../diagrams/ARCHITECTURE.md), [Sequence](../diagrams/SEQUENCE.md) và [báo cáo](../report/REPORT.md).
- Ghi lệnh/ngày/môi trường, Payment ID, trạng thái cuối và các số dư/học phí, không ghi OTP/JWT/secret.
- Tách kết quả Playwright API giả lập với luồng live PostgreSQL/Mailpit; ảnh UI không chứng minh concurrency.
- Kiểm tra [biên bản kiểm chứng](../report/VERIFICATION.md) và [đối chiếu tiêu chí](../report/RUBRIC_AUDIT.md), chỉ trình bày các gate đã thực chạy. Báo ca chưa chạy hoặc chưa đạt.

Không có cloud, SMTP thật hoặc exactly-once email trong phạm vi demo này. Dữ liệu runtime giữ lại qua restart; test stack tách biệt để các kịch bản không làm mất dữ liệu demo.
