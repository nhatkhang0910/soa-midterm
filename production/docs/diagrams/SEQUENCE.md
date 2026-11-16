# Sequence: thanh toán, hủy và phục hồi

Bản SVG: [thành công](rendered/sequence-1.svg), [hủy](rendered/sequence-2.svg), [phục hồi](rendered/sequence-3.svg).

## Luồng thành công

```mermaid
sequenceDiagram
    actor U as Người nộp
    participant UI as Web / Nginx
    participant P as Payment API / DB
    participant PW as Payment worker
    participant T as Tuition / DB
    participant W as Wallet / DB
    participant N as Notification API / DB
    participant NW as Notification worker
    participant M as Mailpit
    U->>UI: Đăng nhập, tra MSSV, đồng ý điều khoản
    UI->>P: POST payments + JWT + Idempotency-Key
    Note over P,W: Backend đọc Auth/Tuition/Wallet qua REST, lấy snapshot và kiểm tra
    P->>P: TX Payment + HMAC challenge + encrypted OTP outbox
    P-->>UI: 201 PENDING_OTP, otpExpiresAt
    PW->>N: PUT messages(eventId, encryptedPayload)
    N->>N: TX lưu job / dedup
    N-->>PW: 200 ACK bền vững
    PW->>P: TX DELIVERED, xóa payload outbox
    NW->>M: SMTP email OTP ngoài transaction
    NW->>N: TX SENT, xóa payload job
    U->>UI: Nhập OTP từ Mailpit
    UI->>P: POST confirm
    P->>P: TX khóa payment/challenge, USED + PREPARING
    P-->>UI: 202 PROCESSING
    PW->>T: PUT reservation RESERVED
    T->>T: TX khóa invoice, giữ quyền thanh toán
    T-->>PW: ACK
    PW->>W: PUT reservation RESERVED
    W->>W: TX khóa wallet, kiểm tra available, tăng reserved
    W-->>PW: ACK
    PW->>P: TX ghi COMMITTING trước deadline
    PW->>W: PUT reservation CAPTURED
    W->>W: TX giảm balance/reserved + debit duy nhất
    W-->>PW: ACK
    PW->>T: PUT reservation PAID
    T->>T: TX invoice PAID
    T-->>PW: ACK
    PW->>P: TX SUCCEEDED + success outbox
    UI->>P: GET payment (poll 2 giây)
    P-->>UI: SUCCEEDED + snapshot
    Note over PW,M: Success outbox đi cùng cơ chế lưu job rồi SMTP, email lỗi không đảo ngược tiền
```

Mỗi ACK/checkpoint được ghi bằng transaction cục bộ ngắn. Không có transaction hoặc row lock kéo dài qua HTTP/SMTP. Tạo Payment chưa giữ tiền; số dư được kiểm tra lại khi Saga reserve.

## Hủy trước COMMITTING

```mermaid
sequenceDiagram
    participant PW as Payment worker
    participant P as Payment DB
    participant T as Tuition
    participant W as Wallet
    PW->>T: Reserve invoice
    T-->>PW: ACK hoặc response bị mất
    PW->>W: Reserve wallet
    W-->>PW: Lỗi nghiệp vụ / timeout
    Note over PW,P: Lỗi nghiệp vụ hoặc quá 30 giây chuẩn bị
    PW->>P: TX ABORTING, checkpoint=0
    PW->>W: CANCELLED cùng paymentId
    W-->>PW: ACK (tạo tombstone nếu chưa reserve)
    PW->>T: CANCELLED cùng paymentId
    T-->>PW: ACK (giải phóng hoặc tạo tombstone)
    PW->>P: TX FAILED sau cả hai ACK
    Note over T,W: Lệnh reserve đến muộn<br/>bị CANCELLED chặn<br/>Reservation không tự hết hạn
```

Timeout không chứng minh lệnh từ xa thất bại. Khi còn PREPARING và chưa quá deadline, worker có thể retry cùng ID; khi đã quyết định ABORTING thì hủy cả hai bên kể cả chưa biết reserve có thành công hay không.

## Forward recovery từ COMMITTING

```mermaid
sequenceDiagram
    participant PW as Payment worker
    participant P as Payment DB
    participant W as Wallet
    participant T as Tuition
    PW->>P: COMMITTING đã commit bền vững
    PW->>W: CAPTURED(paymentId)
    W->>W: Commit debit một lần
    Note over PW,W: Mất response hoặc worker crash trước lưu checkpoint
    Note over P: Lease hết hạn, worker mới claim bằng token mới
    PW->>W: Retry CAPTURED cùng paymentId/payload
    W-->>PW: ACK trạng thái cũ, không debit lần hai
    PW->>P: Lưu checkpoint
    PW->>T: PAID cùng paymentId
    T-->>PW: ACK idempotent
    PW->>P: TX SUCCEEDED + success outbox
    Note over PW,T: Lỗi tạm thời tiếp tục backoff/retry, không refund, không mở invoice
```

Claim dùng khóa `SKIP LOCKED`, lease và token; ghi checkpoint kiểm tra token/lease để worker cũ không thay quyết định mới. Chuyển COMMITTING là điểm quyết định: sự cố kéo dài giữ PROCESSING để phục hồi/đối soát, không biến thành FAILED vì hết lượt retry. Bảo đảm bút toán một lần dựa trên DB/idempotency; không tuyên bố SMTP exactly-once.
