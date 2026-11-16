# iBanking — Thanh toán học phí

Ứng dụng mô phỏng cho đồ án SOA. Năm service FastAPI với năm database/user PostgreSQL 18 riêng; React/TypeScript, Nginx, REST Saga và outbox bền vững. Email **giả qua Mailpit**, theo lựa chọn của người dùng ngày 16/11/2026; không cần tài khoản SMTP hoặc gửi thư ra ngoài.

## Khởi chạy trên Windows

Cần Docker Desktop đang chạy và Python 3.13 cho bước tạo cấu hình. Từ thư mục `production`:

```powershell
py -3.13 -m venv .runtime
.runtime\Scripts\python.exe -m pip install cryptography==50.0.2
.runtime\Scripts\python.exe setup.py
docker compose --env-file .env -f compose.yaml up -d --build --wait
```

`setup.py` tạo credential ngẫu nhiên và cặp khóa JWT cục bộ; không ghi đè `.env` đã tồn tại. Lần build đầu cần Internet để tải image/dependency. Những lần sau chỉ cần lệnh Compose cuối. Migrations và seed tự chạy trước khi mỗi API khởi động; seed không đặt lại số dư/trạng thái đã thay đổi.

- Web: [http://localhost:8080](http://localhost:8080).
- Hộp thư giả: [http://localhost:8080/mail/](http://localhost:8080/mail/). Mở email OTP tương ứng mã giao dịch, lấy mã sáu chữ số.
- Chỉ cổng web được bind ở `127.0.0.1`; API nội bộ, PostgreSQL và SMTP nằm trong mạng Docker. Đây là bản demo cục bộ qua HTTP.

| Tài khoản | Mật khẩu mặc định | Số dư ban đầu | Email giả |
|---|---|---:|---|
| `an` | `Demo@123456` | 10.000.000 VND | `an@example.test` |
| `binh` | `Demo@123456` | 10.000.000 VND | `binh@example.test` |

| MSSV | Dữ liệu ban đầu |
|---|---|
| `52200001`, `52200002` | Mỗi khoản học phí 6.000.000 VND, chưa trả |
| `52200003` | Đã thanh toán |
| `52200004` | Có sinh viên, không có khoản học phí |

Đăng nhập tại `/login` → trang tổng quan `/` hiển thị số dư khả dụng, số dư, số tiền đang giữ và tối đa năm giao dịch mới nhất từ server → chọn **Thanh toán học phí** → tại `/tuition`, nhập MSSV của mình hoặc người khác → tra cứu → đồng ý điều khoản → tiếp tục xác thực → lấy OTP trong Mailpit → xác nhận. Sau thành công, về trang tổng quan để đối chiếu số dư và cùng giao dịch trong danh sách mới nhất; với dữ liệu seed mới, trả 6.000.000 VND từ ví 10.000.000 VND thì còn 4.000.000 VND, đang giữ 0.

Trang tổng quan yêu cầu đăng nhập. **Lịch sử giao dịch** ở `/tuition?view=history&page=N` có phân trang và cho phép mở lại biên nhận/giao dịch chờ; URL cũ `/?view=history` chuyển tới lịch sử mới. Các liên kết điều hướng hỗ trợ nút Quay lại của trình duyệt. Web giữ trạng thái đang xử lý và hỏi lại server mỗi hai giây. JWT chỉ ở bộ nhớ trình duyệt; tải lại trang cần đăng nhập lại. Payment ID đang chờ được lưu riêng theo người dùng để tiếp tục sau đăng nhập bằng liên kết **Tiếp tục giao dịch** trên trang tổng quan; mở biên nhận cũ không làm mất giao dịch hiện tại.

OTP hiển thị sáu ô số trong một trường nhập: có thể nhập hoặc dán cả mã, giữ số 0 đầu và sửa bằng bàn phím. Nhập đủ mã rồi chọn **Xác nhận thanh toán** hoặc nhấn Enter; giao diện không tự gửi khi vừa đủ sáu số. Khi đang xác thực hoặc mã đến hạn, vùng nhập và nút xác nhận tạm khóa; trạng thái cuối lấy từ server.

## Vận hành

```powershell
docker compose ps
docker compose logs --tail 40 payment-worker notification-worker
docker compose stop
docker compose start
```

Volume PostgreSQL giữ dữ liệu qua stop/start hoặc down. Khi có request timeout, thử lại cùng giao dịch; không sửa dữ liệu tài chính bằng tay. `COMMITTING` tiếp tục phục hồi tới kết quả cuối; email lỗi không đảo tiền. Worker log mã lỗi và ID, không log OTP/mật khẩu/token. Mailpit là hộp thư chung của bản mô phỏng trên máy này.
