import { useEffect, useRef, useState } from 'react';
import type { AnchorHTMLAttributes, FormEvent, ReactNode } from 'react';
import { ApiError, date, isPending, money, statusText } from './models';
import type { Payment, PaymentHistory, Profile, Tuition, View, Wallet } from './models';
import { OtpCodeInput } from './OtpCodeInput';

type Navigation = { onNavigate: (href: string) => void };

function Link({ onNavigate, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & Navigation) {
  return <a {...props} onClick={event => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.currentTarget.hasAttribute('download') || event.currentTarget.hasAttribute('target')) return;
    event.preventDefault();
    onNavigate(event.currentTarget.getAttribute('href') || '/');
  }} />;
}

function Icon({ name, size = 21 }: { name: 'bank' | 'home' | 'tuition' | 'history' | 'logout' | 'shield' | 'check' | 'arrow' | 'clock'; size?: number }) {
  const paths = {
    bank: <path d="m3 9 9-6 9 6M4 10h16M5 19h14M3 22h18M7 10v9m5-9v9m5-9v9" />,
    home: <><path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8" /></>,
    tuition: <><path d="m2 8 10-5 10 5-10 5L2 8Z" /><path d="M6 10v7c4 3 8 3 12 0v-7m4-2v9" /></>,
    history: <path d="M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2" />,
    logout: <path d="M9 4H4v16h5m5-12 4 4-4 4M8 12h12" />,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function ErrorMessage({ error, id }: { error: Error | null; id?: string }) {
  if (!error) return null;
  return <div id={id} className="error-message" role="alert"><strong>Không thể hoàn tất yêu cầu</strong><p>{error.message}</p>{error instanceof ApiError && error.requestId && <small>Mã hỗ trợ: {error.requestId}</small>}</div>;
}

function PageHeading({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="page-heading"><div><h1 id="page-heading" tabIndex={-1}>{title}</h1>{children && <p>{children}</p>}</div></div>;
}

export interface AppShellProps extends Navigation {
  profile: Profile;
  view: View;
  children: ReactNode;
  onLogout: () => void;
  recoveryError: Error | null;
  recoveryBusy: boolean;
  onRetryPayment: () => void;
}

export function AppShell({ profile, view, children, onNavigate, onLogout, recoveryError, recoveryBusy, onRetryPayment }: AppShellProps) {
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const accountButtonRef = useRef<HTMLButtonElement>(null);
  const routeKey = location.pathname + location.search;

  useEffect(() => { setAccountOpen(false); }, [routeKey]);
  useEffect(() => {
    if (!accountOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    }
    function onHashChange() { setAccountOpen(false); }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setAccountOpen(false);
        accountButtonRef.current?.focus();
      }
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('hashchange', onHashChange);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('hashchange', onHashChange);
    };
  }, [accountOpen]);

  return <div className="app-shell">
    <a className="skip-link" href="#main">Đến nội dung chính</a>
    <header className="app-header"><div className="header-inner">
      <Link className="brand" href="/" onNavigate={onNavigate} aria-label="iBanking trang chủ"><span className="brand-icon"><Icon name="bank" size={25} /></span>iBanking</Link>
      <nav className="main-nav" aria-label="Điều hướng chính">
        <Link href="/" onNavigate={onNavigate} aria-current={view === 'home' ? 'page' : undefined}><Icon name="home" /><span>Tổng quan</span></Link>
        <Link href="/tuition" onNavigate={onNavigate} aria-current={view === 'payment' ? 'page' : undefined}><Icon name="tuition" /><span>Thanh toán học phí</span></Link>
        <Link href="/tuition?view=history&page=1" onNavigate={onNavigate} aria-current={view === 'history' ? 'page' : undefined}><Icon name="history" /><span>Lịch sử giao dịch</span></Link>
      </nav>
      <div className="account-disclosure" ref={accountRef}>
        <button type="button" className="account-trigger" aria-label="Tài khoản" aria-expanded={accountOpen} aria-controls="account-panel" ref={accountButtonRef} onClick={() => setAccountOpen(open => !open)}><span className="avatar" aria-hidden="true">{profile.fullName.trim().split(/\s+/).at(-1)?.slice(0, 1)}</span></button>
        {accountOpen && <div className="account-panel" id="account-panel"><p className="account-name">{profile.fullName}</p><p className="account-email">{profile.email}</p><button className="account-logout" onClick={onLogout}><Icon name="logout" size={18} />Đăng xuất</button></div>}
      </div>
    </div></header>
      <main id="main" className="main-content" tabIndex={-1}>{recoveryError && <div className="recovery-notice"><ErrorMessage error={recoveryError} /><p className="helper">Chưa tải được giao dịch trước đó. Bạn có thể tải lại để tiếp tục.</p><button className="secondary" disabled={recoveryBusy} onClick={onRetryPayment}>{recoveryBusy ? 'Đang tải giao dịch…' : 'Tải lại giao dịch'}</button></div>}{children}<footer className="app-footer"><span>iBanking · Ngân hàng trực tuyến</span><span>Ứng dụng mô phỏng phục vụ học tập</span></footer></main>
  </div>;
}

export interface LoginPageProps {
  username: string;
  password: string;
  showPassword: boolean;
  busy: boolean;
  error: Error | null;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onTogglePassword: () => void;
  onSubmit: (event: FormEvent) => void;
}

export function LoginPage({ username, password, showPassword, busy, error, onUsernameChange, onPasswordChange, onTogglePassword, onSubmit }: LoginPageProps) {
  const invalid = error instanceof ApiError && error.code === 'LOGIN_INVALID';
  return <main className="login-layout">
    <header className="login-header"><a className="brand" href="/" aria-label="iBanking trang chủ"><span className="brand-icon"><Icon name="bank" size={25} /></span>iBanking</a></header>
    <section className="login-form-wrap" aria-labelledby="page-heading">
      <form className="login-form" onSubmit={onSubmit} aria-busy={busy} aria-labelledby="page-heading">
        <div className="login-emblem" aria-hidden="true"><Icon name="bank" size={27} /></div>
        <h1 id="page-heading" tabIndex={-1}>Đăng nhập</h1><p className="muted">Truy cập tài khoản và thanh toán học phí.</p>
        <ErrorMessage error={error} id="login-error" />
        <label htmlFor="username">Tên đăng nhập</label><input id="username" autoComplete="username" required maxLength={128} value={username} onChange={event => onUsernameChange(event.target.value)} aria-invalid={invalid || undefined} aria-describedby={error ? 'login-error' : undefined} />
        <label htmlFor="password">Mật khẩu</label><div className="password-field"><input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required maxLength={256} value={password} onChange={event => onPasswordChange(event.target.value)} aria-invalid={invalid || undefined} aria-describedby={error ? 'login-error' : undefined} /><button className="text-button" type="button" aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={showPassword} onClick={onTogglePassword}>{showPassword ? 'Ẩn' : 'Hiện'}</button></div>
        <button className="primary login-submit" disabled={busy} aria-busy={busy}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}<Icon name="arrow" /></button>
        <p className="login-security"><Icon name="shield" size={16} />Xác thực giao dịch qua email OTP</p>
        <p className="login-help">Thông tin tài khoản do nhóm triển khai cung cấp.</p>
        <p className="demo-note">Ứng dụng mô phỏng phục vụ học tập. Sử dụng tài khoản được cấp sẵn.</p>
      </form>
    </section>
  </main>;
}

function WalletSummary({ wallet, error, onRetry, compact = false }: { wallet: Wallet | null; error: Error | null; onRetry: () => void; compact?: boolean }) {
  return <section className={`wallet-summary ${compact ? 'compact-wallet' : ''}`} aria-label="Thông tin số dư">
    <div className="balance-panel"><div className="balance-heading"><span>Số dư khả dụng</span><Icon name="bank" size={23} /></div>
      {wallet ? <p className="balance-number">{money(wallet.available)} <small>VND</small></p> : !error && <div className="balance-loading" role="status">Đang tải số dư…</div>}
      {error && <><ErrorMessage error={error} /><button className="balance-retry" onClick={onRetry}>Tải lại số dư</button></>}
    </div>
  </section>;
}

function StatusBadge({ payment }: { payment: Payment }) {
  return <span className={`badge ${payment.status === 'SUCCEEDED' ? 'success' : payment.status === 'FAILED' || payment.status === 'EXPIRED' ? 'failed' : ''}`}>{statusText[payment.status]}</span>;
}

export interface HomePageProps extends Navigation {
  profile: Profile;
  wallet: Wallet | null;
  walletError: Error | null;
  recent: PaymentHistory | null;
  recentBusy: boolean;
  recentError: Error | null;
  activePayment: Payment | null;
  onRetryWallet: () => void;
  onRetryRecent: () => void;
  onContinue: () => void;
}

export function HomePage({ wallet, walletError, recent, recentBusy, recentError, activePayment, onNavigate, onRetryWallet, onRetryRecent, onContinue }: HomePageProps) {
  return <>
    <PageHeading title="Tổng quan tài khoản" />
    <div className="overview-layout">
      <WalletSummary wallet={wallet} error={walletError} onRetry={onRetryWallet} />
      <div className="tuition-shortcut"><Link className="primary" href="/tuition" onNavigate={onNavigate}>Thanh toán học phí<Icon name="arrow" size={18} /></Link></div>
    </div>
    {activePayment && <div className="active-notice"><Icon name="clock" /><div><strong>{activePayment.status === 'PENDING_OTP' ? 'Bạn có giao dịch đang chờ xác thực' : 'Giao dịch đang được xử lý'}</strong><p>{activePayment.student.fullName} · {money(activePayment.amount)} VND</p></div><Link className="text-button" href="/tuition" onNavigate={onContinue}>Tiếp tục giao dịch<Icon name="arrow" size={17} /></Link></div>}
    <section className="history-section recent-section" aria-labelledby="recent-heading"><div className="history-heading"><h2 id="recent-heading">Giao dịch gần đây</h2><Link className="text-button" href="/tuition?view=history&page=1" onNavigate={onNavigate}>Xem tất cả giao dịch<Icon name="arrow" size={17} /></Link></div>
      <ErrorMessage error={recentError} />{recentError && <div className="retry-row"><button className="secondary" onClick={onRetryRecent} disabled={recentBusy}>Tải lại giao dịch</button></div>}
      {recentBusy ? <div className="table-loading" role="status">Đang tải giao dịch…</div> : recent && recent.items.length > 0 ? <div className="table-scroll"><table className="ledger-table"><thead><tr><th scope="col">Sinh viên / giao dịch</th><th scope="col">Thời gian</th><th scope="col" className="number">Số tiền</th><th scope="col">Trạng thái</th></tr></thead><tbody>{recent.items.slice(0, 5).map(item => <tr key={item.id}><td><strong>{item.student.fullName}</strong><small>MSSV {item.student.mssv}</small><small className="transaction-id">{item.id}</small></td><td><span className="mobile-cell-label" aria-hidden="true">Thời gian</span>{date(item.createdAt)}</td><td className="number"><span className="mobile-cell-label" aria-hidden="true">Số tiền</span><span>{money(item.amount)} <small>VND</small></span></td><td><span className="mobile-cell-label" aria-hidden="true">Trạng thái</span><StatusBadge payment={item} /></td></tr>)}</tbody></table></div> : !recentError && <div className="empty-state"><Icon name="history" size={34} /><h3>Chưa có giao dịch</h3><p>Các giao dịch thanh toán học phí của bạn sẽ xuất hiện tại đây.</p><Link className="secondary" href="/tuition" onNavigate={onNavigate}>Thanh toán học phí</Link></div>}
    </section>
  </>;
}

export interface TuitionPageProps extends Navigation {
  profile: Profile;
  wallet: Wallet | null;
  walletError: Error | null;
  mssv: string;
  tuition: Tuition | null;
  terms: boolean;
  payment: Payment | null;
  activePayment: Payment | null;
  receiptOnly: boolean;
  otp: string;
  seconds: number;
  busy: boolean;
  error: Error | null;
  onMssvChange: (value: string) => void;
  onTermsChange: (value: boolean) => void;
  onOtpChange: (value: string) => void;
  onLookup: (event: FormEvent) => void;
  onCreate: (event: FormEvent) => void;
  onConfirm: (event: FormEvent) => void;
  onStartAgain: () => void;
  onRetryWallet: () => void;
  onContinue: () => void;
}

export function TuitionPage({ profile, wallet, walletError, mssv, tuition, terms, payment, activePayment, receiptOnly, otp, seconds, busy, error, onMssvChange, onTermsChange, onOtpChange, onLookup, onCreate, onConfirm, onStartAgain, onNavigate, onRetryWallet, onContinue }: TuitionPageProps) {
  const canPay = tuition?.invoice?.status === 'UNPAID' && !!wallet && wallet.available >= tuition.invoice.amount;
  const otpInvalid = error instanceof ApiError && error.code === 'OTP_INVALID';
  const lookupError = !payment && error instanceof ApiError && error.code === 'STUDENT_NOT_FOUND';
  return <>
    <PageHeading title="Thanh toán học phí">Kiểm tra thông tin, xác thực và hoàn tất thanh toán.</PageHeading>
    <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{payment ? `Giao dịch: ${statusText[payment.status]}.` : tuition ? `${tuition.student.fullName}: ${!tuition.invoice ? 'Không có khoản thu.' : tuition.invoice.status === 'PAID' ? 'Đã thanh toán.' : tuition.invoice.status === 'RESERVED' ? 'Đang được thanh toán.' : `Học phí ${money(tuition.invoice.amount)} VND, chưa thanh toán.`}` : ''}</p>
    {payment && isPending(payment) && <div className="active-notice"><Icon name="clock" /><span>Giao dịch {payment.status === 'PENDING_OTP' ? 'đang chờ xác thực' : 'đang được xử lý'}. Bạn có thể xem lại từ lịch sử.</span></div>}
    <div className="payment-layout"><div className="payment-main">
      {!payment ? <div className="tuition-form-surface">
        <section className="payer-section"><div className="section-heading"><h2>Thông tin người nộp</h2><span className="read-only">Từ tài khoản đăng nhập</span></div><dl className="details-grid"><div><dt>Họ và tên</dt><dd>{profile.fullName}</dd></div><div><dt>Số điện thoại</dt><dd>{profile.phone || 'Chưa cập nhật'}</dd></div><div className="wide"><dt>Email nhận OTP và kết quả</dt><dd>{profile.email}</dd></div></dl></section>
        <section className="lookup-section"><div className="section-heading"><h2>Thông tin học phí</h2></div><form onSubmit={onLookup}><label htmlFor="mssv">Mã số sinh viên cần thanh toán</label><div className="lookup-row"><input id="mssv" disabled={busy} inputMode="numeric" autoComplete="off" required maxLength={32} value={mssv} aria-describedby={`mssv-help${lookupError ? ' payment-error' : ''}`} aria-invalid={lookupError || undefined} onChange={event => onMssvChange(event.target.value)} placeholder="52200001" /><button className="secondary" disabled={busy} aria-busy={busy}>{busy ? 'Đang tra cứu…' : 'Tra cứu'}</button></div><p className="helper" id="mssv-help">Bạn có thể thanh toán cho mình hoặc sinh viên khác.</p></form>
          {tuition && <div className="tuition-result"><div className="student-line"><div><p className="muted small">Sinh viên</p><h3>{tuition.student.fullName}</h3><p className="muted small">MSSV {tuition.student.mssv}</p></div><span className={`badge ${tuition.invoice?.status === 'PAID' ? 'success' : ''}`}>{!tuition.invoice ? 'Không có khoản thu' : tuition.invoice.status === 'PAID' ? 'Đã thanh toán' : tuition.invoice.status === 'RESERVED' ? 'Đang được thanh toán' : 'Chưa thanh toán'}</span></div>{tuition.invoice ? <div className="invoice-amount"><span>Học phí hiện hành</span><strong>{money(tuition.invoice.amount)} <small>VND</small></strong></div> : <p className="helper">Sinh viên hiện không có khoản học phí cần thanh toán.</p>}{tuition.invoice?.status === 'RESERVED' && <p className="helper">Khoản học phí đang có giao dịch xử lý. Vui lòng kiểm tra lại sau.</p>}</div>}
        </section>
        <section className="confirmation-section"><div className="section-heading"><h2>Xác nhận thanh toán</h2></div><p className="muted">Thanh toán toàn bộ học phí bằng số dư khả dụng. Kiểm tra kỹ sinh viên và số tiền trước khi tiếp tục.</p><form onSubmit={onCreate}><label className="terms"><input type="checkbox" required checked={terms} onChange={event => onTermsChange(event.target.checked)} disabled={!canPay || busy} /><span>Tôi đồng ý thanh toán toàn bộ khoản học phí trên và xác nhận thông tin sinh viên là chính xác.</span></label>{tuition?.invoice?.status === 'UNPAID' && wallet && wallet.available < tuition.invoice.amount && <p className="inline-error" role="status">Số dư khả dụng không đủ để thanh toán khoản học phí này.</p>}<ErrorMessage error={error} id="payment-error" /><div className="form-footer"><p className="helper"><Icon name="shield" size={17} />Xác thực bằng OTP gửi đến email của bạn</p><button className="primary" disabled={!canPay || busy} aria-busy={busy}>{busy ? 'Đang tạo giao dịch…' : 'Tiếp tục xác thực'}<Icon name="arrow" size={18} /></button></div></form></section>
      </div> : <section className={`section payment-state${payment.status === 'PENDING_OTP' ? ' otp-panel' : ' terminal-state'}`}>
        {payment.status === 'PENDING_OTP' ? <>
          <div className="state-symbol"><Icon name="shield" size={30} /></div>
          <h2 id="payment-heading" tabIndex={-1}>Xác thực thanh toán</h2>
          <p className="muted">Mã OTP 6 chữ số đã được yêu cầu gửi đến <strong>{payment.payer.email}</strong>.</p>
          <PaymentSummary payment={payment} />
          <form className="otp-form" onSubmit={onConfirm} aria-busy={busy}>
            <label htmlFor="otp">Mã OTP</label>
            <p className="helper otp-help" id="otp-help">Nhập hoặc dán mã gồm 6 chữ số từ email.</p>
            <OtpCodeInput value={otp} onChange={onOtpChange} disabled={busy || seconds === 0} invalid={otpInvalid} describedBy={`otp-help otp-time${error ? ' payment-error' : ''}`} />
            <p id="otp-time" className={`countdown ${seconds === 0 ? 'inline-error' : ''}`}>{seconds > 0 ? <>Mã có hiệu lực trong <strong>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</strong></> : 'Mã đã đến hạn. Đang kiểm tra trạng thái giao dịch…'}</p>
            <ErrorMessage error={error} id="payment-error" />
            <p className="otp-feedback" role="status">{busy ? 'Đang kiểm tra mã xác thực…' : ''}</p>
            <button className="primary full otp-submit" disabled={busy || seconds === 0 || otp.length !== 6} aria-busy={busy}>{busy ? 'Đang xác thực…' : 'Xác nhận thanh toán'}</button>
          </form>
          <p className="helper otp-security">Không chia sẻ mã OTP. Mỗi giao dịch sử dụng một mã duy nhất.</p>
        </> : <>
          <div className={`state-symbol ${payment.status === 'SUCCEEDED' ? 'complete' : ''}`}><Icon name={payment.status === 'SUCCEEDED' ? 'check' : 'clock'} size={32} /></div><h2 id="payment-heading" tabIndex={-1}>{payment.status === 'SUCCEEDED' ? 'Thanh toán thành công' : payment.status === 'PROCESSING' ? 'Giao dịch đang được xử lý' : payment.status === 'EXPIRED' ? 'Mã xác thực đã hết hạn' : 'Thanh toán không thành công'}</h2><p className="muted">{payment.status === 'SUCCEEDED' ? 'Học phí đã được thanh toán. Kết quả sẽ được gửi đến email của bạn.' : payment.status === 'PROCESSING' ? 'Hệ thống đang hoàn tất giao dịch. Trạng thái tự cập nhật mỗi 2 giây; bạn có thể quay lại từ lịch sử.' : payment.status === 'EXPIRED' ? 'Giao dịch chưa được xác thực. Bạn có thể tạo giao dịch mới để nhận mã OTP mới.' : payment.failureCode === 'OTP_LOCKED' ? 'Mã OTP đã nhập sai quá số lần cho phép. Vui lòng tạo giao dịch mới.' : 'Giao dịch chưa hoàn tất. Kiểm tra số dư và thông tin học phí trước khi thử lại.'}</p><PaymentSummary payment={payment} /><ErrorMessage error={error} id="payment-error" /><div className="result-actions"><Link className="secondary" href="/tuition?view=history&page=1" onNavigate={onNavigate}>{receiptOnly ? 'Trở về lịch sử giao dịch' : 'Xem lịch sử giao dịch'}</Link>{receiptOnly && activePayment ? <Link className="primary" href="/tuition" onNavigate={onContinue}>Tiếp tục giao dịch đang xử lý</Link> : !receiptOnly && payment.status !== 'PROCESSING' && <button className="primary" onClick={onStartAgain}>Thanh toán khoản khác</button>}{receiptOnly && !activePayment && <Link className="primary" href="/tuition" onNavigate={onNavigate}>Thanh toán học phí</Link>}</div>
        </>}
      </section>}
    </div><aside className="account-summary"><WalletSummary wallet={wallet} error={walletError} onRetry={onRetryWallet} compact /></aside></div>
  </>;
}

function PaymentSummary({ payment }: { payment: Payment }) {
  return <dl className="payment-receipt"><div><dt>Sinh viên</dt><dd>{payment.student.fullName}<small>MSSV {payment.student.mssv}</small></dd></div><div><dt>Người nộp</dt><dd>{payment.payer.fullName}</dd></div><div><dt>Thời gian tạo</dt><dd>{date(payment.createdAt)}</dd></div><div><dt>Mã giao dịch</dt><dd className="transaction-id">{payment.id}</dd></div><div className="receipt-total"><dt>Số tiền thanh toán</dt><dd>{money(payment.amount)} <small>VND</small></dd></div></dl>;
}

export interface HistorySectionProps extends Navigation {
  history: PaymentHistory | null;
  historyBusy: boolean;
  historyError: Error | null;
  page: number;
  busy: boolean;
  onRefresh: () => void;
  onPageChange: (page: number) => void;
  onOpenPayment: (payment: Payment) => void;
}

export function HistorySection({ history, historyBusy, historyError, page, busy, onRefresh, onPageChange, onOpenPayment, onNavigate }: HistorySectionProps) {
  return <>
    <PageHeading title="Lịch sử giao dịch">Theo dõi các giao dịch học phí từ tài khoản của bạn.</PageHeading>
    <section className="history-section"><div className="history-heading"><h2>Giao dịch học phí</h2><button className="secondary" disabled={historyBusy} onClick={onRefresh} aria-busy={historyBusy}>{historyBusy ? 'Đang tải…' : 'Làm mới'}</button></div><ErrorMessage error={historyError} />
      {historyBusy ? <div className="table-loading" role="status">Đang tải lịch sử giao dịch…</div> : history && history.items.length ? <><div className="table-scroll"><table className="ledger-table"><thead><tr><th scope="col">Sinh viên / giao dịch</th><th scope="col">Thời gian</th><th scope="col" className="number">Số tiền</th><th scope="col">Trạng thái</th><th scope="col"><span className="sr-only">Chi tiết</span></th></tr></thead><tbody>{history.items.map(item => <tr key={item.id}><td><strong>{item.student.fullName}</strong><small>MSSV {item.student.mssv}</small><small className="transaction-id">{item.id}</small></td><td><span className="mobile-cell-label" aria-hidden="true">Thời gian</span>{date(item.createdAt)}</td><td className="number"><span className="mobile-cell-label" aria-hidden="true">Số tiền</span><span>{money(item.amount)}<small>VND</small></span></td><td><span className="mobile-cell-label" aria-hidden="true">Trạng thái</span><StatusBadge payment={item} /></td><td className="row-action"><button className="text-button" disabled={busy} aria-label={`Xem giao dịch ${item.id}`} onClick={() => onOpenPayment(item)}>{isPending(item) ? 'Tiếp tục' : 'Chi tiết'}</button></td></tr>)}</tbody></table></div><div className="pagination"><span>{history.total} giao dịch</span><div><button className="secondary" disabled={page <= 1 || historyBusy} onClick={() => onPageChange(page - 1)}>Trước</button><span>Trang {page} / {Math.max(1, Math.ceil(history.total / history.pageSize))}</span><button className="secondary" disabled={page * history.pageSize >= history.total || historyBusy} onClick={() => onPageChange(page + 1)}>Sau</button></div></div></> : !historyError && <div className="empty-state"><Icon name="history" size={34} /><h3>Chưa có giao dịch</h3><p>Các giao dịch thanh toán học phí của bạn sẽ xuất hiện tại đây.</p><Link className="primary" href="/tuition" onNavigate={onNavigate}>Thanh toán học phí</Link></div>}
    </section>
  </>;
}
