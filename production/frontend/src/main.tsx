import React, { FormEvent, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ApiError, isPending } from './models';
import type { Payment, PaymentHistory, Profile, Tuition, Wallet } from './models';
import { guardRoute, historyHref, resolveRoute } from './routing';
import type { Route } from './routing';
import { AppShell, HomePage, HistorySection, LoginPage, TuitionPage } from './pages';
import './styles.css';

async function request<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/api/v1${path}`, { ...options, signal: controller.signal, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(data?.message || 'Dịch vụ tạm thời chưa sẵn sàng. Vui lòng thử lại.', response.status, data?.code || 'SERVICE_UNAVAILABLE', data?.requestId);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Chưa nhận được phản hồi do mất kết nối. Vui lòng thử lại; yêu cầu thanh toán được giữ nguyên.', 0, 'NETWORK_ERROR');
  } finally { window.clearTimeout(timer); }
}

const makeIdempotencyKey = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
const stored = {
  read(key: string) { try { return sessionStorage.getItem(key); } catch { return null; } },
  write(key: string, value: string) { try { sessionStorage.setItem(key, value); } catch { /* Memory still preserves retries in this session. */ } },
  remove(key: string) { try { sessionStorage.removeItem(key); } catch { /* Storage can be unavailable in private browsing. */ } },
};

function App() {
  const [route, setRoute] = useState(resolveRoute);
  const routeRef = useRef(route);
  const [token, setToken] = useState('');
  const tokenRef = useRef('');
  const sessionVersion = useRef(0);
  const navigationVersion = useRef(0);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [walletError, setWalletError] = useState<Error | null>(null);
  const walletGeneration = useRef(0);
  const [historyList, setHistoryList] = useState<PaymentHistory | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState<Error | null>(null);
  const historyGeneration = useRef(0);
  const [recent, setRecent] = useState<PaymentHistory | null>(null);
  const [recentBusy, setRecentBusy] = useState(false);
  const [recentError, setRecentError] = useState<Error | null>(null);
  const recentGeneration = useRef(0);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mssv, setMssv] = useState('');
  const [tuition, setTuition] = useState<Tuition | null>(null);
  const lookupGeneration = useRef(0);
  const [terms, setTerms] = useState(false);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [viewedPayment, setViewedPayment] = useState<Payment | null>(null);
  const [recoveryError, setRecoveryError] = useState<Error | null>(null);
  const pollInFlight = useRef(false);
  const [otp, setOtp] = useState('');
  const [now, setNow] = useState(Date.now());
  const [focusVersion, setFocusVersion] = useState(0);
  const attemptKeys = useRef(new Map<string, string>());

  async function api<T>(path: string, accessToken: string, options: RequestInit = {}): Promise<T> {
    const version = sessionVersion.current;
    try {
      const result = await request<T>(path, accessToken, options);
      if (version !== sessionVersion.current) throw new ApiError('Phiên giao dịch đã kết thúc.', 499, 'SESSION_ENDED');
      return result;
    } catch (e) {
      if (version !== sessionVersion.current) throw new ApiError('Phiên giao dịch đã kết thúc.', 499, 'SESSION_ENDED');
      throw e;
    }
  }

  function applyRoute(next: Route, mode: 'push' | 'replace' | 'pop') {
    if (next.href !== routeRef.current.href) {
      navigationVersion.current += 1;
      historyGeneration.current += 1; setHistoryBusy(false);
      recentGeneration.current += 1; setRecentBusy(false);
      setViewedPayment(null);
    }
    if (mode === 'push' && next.href !== location.pathname + location.search) window.history.pushState({}, '', next.href);
    else if (mode === 'replace' || next.href !== location.pathname + location.search) window.history.replaceState({}, '', next.href);
    routeRef.current = next; setRoute(next);
  }

  function navigate(href: string) {
    setError(null);
    if (href === '/tuition') setViewedPayment(null);
    applyRoute(guardRoute(resolveRoute(href), Boolean(tokenRef.current)), 'push');
  }

  function logout(message?: string) {
    const destination = message ? routeRef.current.href : '/';
    sessionVersion.current += 1; navigationVersion.current += 1;
    walletGeneration.current += 1; historyGeneration.current += 1; recentGeneration.current += 1; lookupGeneration.current += 1;
    tokenRef.current = ''; locked.current = false;
    setBusy(false); setHistoryBusy(false); setRecentBusy(false);
    setToken(''); setProfile(null); setWallet(null); setHistoryList(null); setRecent(null);
    setPayment(null); setViewedPayment(null); setTuition(null); setMssv(''); setPassword(''); setShowPassword(false); setOtp(''); setTerms(false);
    setError(message ? new Error(message) : null); setRecoveryError(null); setWalletError(null); setHistoryError(null); setRecentError(null); attemptKeys.current.clear();
    applyRoute(guardRoute(resolveRoute(destination), false), 'replace');
  }

  function handleError(value: unknown, target: (error: Error) => void = setError) {
    const next = value instanceof Error ? value : new Error('Đã có lỗi xảy ra. Vui lòng thử lại.');
    if (next instanceof ApiError && next.code === 'SESSION_ENDED') return;
    if (next instanceof ApiError && next.status === 401 && tokenRef.current) logout('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.');
    else target(next);
  }

  useEffect(() => {
    const onPop = () => {
      setError(null);
      applyRoute(guardRoute(resolveRoute(), Boolean(tokenRef.current)), 'pop');
    };
    applyRoute(guardRoute(resolveRoute(), Boolean(tokenRef.current)), 'replace');
    addEventListener('popstate', onPop);
    return () => removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    const title = { home: 'Tổng quan tài khoản', login: 'Đăng nhập', payment: 'Thanh toán học phí', history: 'Lịch sử giao dịch' }[route.view];
    document.title = `${title} | iBanking`;
    const target = route.view === 'payment' && !viewedPayment && payment?.status === 'PENDING_OTP'
      ? document.getElementById('otp')
      : route.view === 'payment' && (viewedPayment || payment)
        ? document.getElementById('payment-heading') : document.getElementById('page-heading');
    target?.focus();
  }, [route.href, profile?.id, focusVersion, viewedPayment?.id]);

  async function refreshWallet(accessToken = tokenRef.current) {
    const generation = ++walletGeneration.current;
    try {
      const next = await api<Wallet>('/wallet', accessToken);
      if (generation === walletGeneration.current) { setWallet(next); setWalletError(null); }
    } catch (e) { if (generation === walletGeneration.current) handleError(e, setWalletError); }
  }

  async function refreshRecent(accessToken = tokenRef.current) {
    const generation = ++recentGeneration.current;
    setRecentBusy(true); setRecentError(null);
    try {
      const next = await api<PaymentHistory>('/payments?page=1&pageSize=5', accessToken);
      if (generation === recentGeneration.current) setRecent(next);
    } catch (e) { if (generation === recentGeneration.current) handleError(e, setRecentError); }
    finally { if (generation === recentGeneration.current) setRecentBusy(false); }
  }

  async function refreshHistory(accessToken = tokenRef.current, requestedPage = routeRef.current.page) {
    const generation = ++historyGeneration.current;
    setHistoryBusy(true); setHistoryError(null);
    try {
      const next = await api<PaymentHistory>(`/payments?page=${requestedPage}&pageSize=10`, accessToken);
      if (generation !== historyGeneration.current) return;
      const lastPage = Math.max(1, Math.ceil(next.total / next.pageSize));
      if (requestedPage > lastPage) { applyRoute(resolveRoute(historyHref(lastPage)), 'replace'); return; }
      setHistoryList(next);
    } catch (e) { if (generation === historyGeneration.current) handleError(e, setHistoryError); }
    finally { if (generation === historyGeneration.current) setHistoryBusy(false); }
  }

  async function restorePayment(accessToken: string, user: Profile) {
    const id = stored.read(`ibanking.current.${user.id}`);
    if (!id) { setRecoveryError(null); return; }
    try {
      setPayment(await api<Payment>(`/payments/${encodeURIComponent(id)}`, accessToken));
      setRecoveryError(null);
      if (routeRef.current.view === 'payment') setFocusVersion(value => value + 1);
    } catch (e) {
      if (e instanceof ApiError && [403, 404].includes(e.status)) { stored.remove(`ibanking.current.${user.id}`); setRecoveryError(null); }
      else handleError(e, setRecoveryError);
    }
  }

  useEffect(() => { if (token && (route.view === 'home' || route.view === 'payment')) void refreshWallet(); }, [token, route.view]);
  useEffect(() => { if (token && route.view === 'home') void refreshRecent(); }, [token, route.view]);
  useEffect(() => { if (token && route.view === 'history') void refreshHistory(); }, [token, route.view, route.page]);

  useEffect(() => {
    if (!payment || !profile) return;
    const currentKey = `ibanking.current.${profile.id}`;
    if (isPending(payment)) stored.write(currentKey, payment.id);
    else {
      if (stored.read(currentKey) === payment.id) stored.remove(currentKey);
      void refreshWallet();
      if (routeRef.current.view === 'home') void refreshRecent();
      if (routeRef.current.view === 'history') void refreshHistory();
      if (tuition) {
        const generation = lookupGeneration.current;
        void api<Tuition>(`/students/${encodeURIComponent(tuition.student.mssv)}/tuition`, token)
          .then(next => { if (generation === lookupGeneration.current) setTuition(next); })
          .catch(e => { if (generation === lookupGeneration.current) handleError(e); });
      }
    }
  }, [payment?.id, payment?.status]);

  useEffect(() => {
    if (!payment || !isPending(payment) || !token) return;
    let stopped = false;
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    const poll = window.setInterval(async () => {
      if (pollInFlight.current) return;
      pollInFlight.current = true;
      try {
        const next = await api<Payment>(`/payments/${encodeURIComponent(payment.id)}`, token);
        if (!stopped) { setPayment(next); setError(current => current instanceof ApiError && current.code === 'NETWORK_ERROR' ? null : current); }
      } catch (e) { if (!stopped) handleError(e); }
      finally { pollInFlight.current = false; }
    }, 2000);
    return () => { stopped = true; window.clearInterval(tick); window.clearInterval(poll); };
  }, [payment?.id, payment?.status, token]);

  async function run(action: () => Promise<void>) {
    if (locked.current) return;
    const version = sessionVersion.current;
    locked.current = true; setBusy(true); setError(null);
    try { await action(); } catch (e) { handleError(e); }
    finally { if (version === sessionVersion.current) { locked.current = false; setBusy(false); } }
  }

  function login(event: FormEvent) {
    event.preventDefault();
    const destination = routeRef.current.view === 'login' ? routeRef.current.returnTo : '/';
    void run(async () => {
      const auth = await api<{ accessToken: string }>('/auth/login', '', { method: 'POST', body: JSON.stringify({ username: username.trim(), password }) });
      const user = await api<Profile>('/me', auth.accessToken);
      tokenRef.current = auth.accessToken;
      setToken(auth.accessToken); setProfile(user); setPassword(''); setShowPassword(false);
      applyRoute(resolveRoute(destination), 'replace');
      await restorePayment(auth.accessToken, user);
    });
  }

  function lookup(event: FormEvent) {
    event.preventDefault();
    const generation = ++lookupGeneration.current;
    void run(async () => {
      setTuition(null); setTerms(false);
      const next = await api<Tuition>(`/students/${encodeURIComponent(mssv.trim())}/tuition`, tokenRef.current);
      if (generation === lookupGeneration.current) setTuition(next);
    });
  }

  function createPayment(event: FormEvent) {
    event.preventDefault();
    if (!terms || !tuition?.invoice) return;
    const invoiceId = tuition.invoice.id;
    void run(async () => {
      const keyName = `ibanking.attempt.${profile!.id}.${invoiceId}`;
      let key = attemptKeys.current.get(invoiceId) || stored.read(keyName);
      if (!key) { key = makeIdempotencyKey(); attemptKeys.current.set(invoiceId, key); stored.write(keyName, key); }
      const created = await api<Payment>('/payments', tokenRef.current, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ invoiceId, acceptedTerms: true }) });
      stored.remove(keyName); attemptKeys.current.delete(invoiceId);
      setPayment(created); setViewedPayment(null); setOtp(''); setNow(Date.now()); setFocusVersion(value => value + 1);
    });
  }

  function confirmPayment(event: FormEvent) {
    event.preventDefault();
    if (!payment || viewedPayment) return;
    void run(async () => {
      try { setPayment(await api<Payment>(`/payments/${encodeURIComponent(payment.id)}/confirm`, tokenRef.current, { method: 'POST', body: JSON.stringify({ otp }) })); setFocusVersion(value => value + 1); }
      catch (e) {
        if (e instanceof ApiError && ['OTP_EXPIRED', 'OTP_LOCKED'].includes(e.code)) { setPayment(await api<Payment>(`/payments/${encodeURIComponent(payment.id)}`, tokenRef.current)); setFocusVersion(value => value + 1); }
        throw e;
      }
    });
  }

  async function openPayment(item: Payment) {
    const navigation = navigationVersion.current;
    await run(async () => {
      setHistoryError(null);
      try {
        const next = await api<Payment>(`/payments/${encodeURIComponent(item.id)}`, tokenRef.current);
        if (navigation !== navigationVersion.current) return;
        navigate('/tuition');
        if (isPending(next)) { setPayment(next); setViewedPayment(null); setOtp(''); setNow(Date.now()); }
        else setViewedPayment(next);
        setFocusVersion(value => value + 1);
      } catch (e) { if (navigation === navigationVersion.current) handleError(e, setHistoryError); }
    });
  }

  function continuePayment() {
    setViewedPayment(null); navigate('/tuition'); setNow(Date.now()); setFocusVersion(value => value + 1);
  }

  function startAgain() {
    setViewedPayment(null);
    if (payment && isPending(payment)) { continuePayment(); return; }
    lookupGeneration.current += 1;
    if (tuition?.invoice && profile) { stored.remove(`ibanking.attempt.${profile.id}.${tuition.invoice.id}`); attemptKeys.current.delete(tuition.invoice.id); }
    setPayment(null); setTuition(null); setMssv(''); setTerms(false); setOtp(''); setError(null); setFocusVersion(value => value + 1);
  }

  if (!profile || route.view === 'login') return <LoginPage username={username} password={password} showPassword={showPassword} busy={busy} error={error}
    onUsernameChange={setUsername} onPasswordChange={setPassword} onTogglePassword={() => setShowPassword(value => !value)} onSubmit={login} />;

  const activePayment = payment && isPending(payment) ? payment : null;
  const displayPayment = viewedPayment || payment;
  const seconds = payment ? Math.max(0, Math.ceil((new Date(payment.otpExpiresAt).getTime() - now) / 1000)) : 0;
  return <AppShell profile={profile} view={route.view} onNavigate={navigate} onLogout={() => logout()}
    recoveryError={recoveryError} recoveryBusy={busy} onRetryPayment={() => void run(() => restorePayment(tokenRef.current, profile))}>
    {route.view === 'home' ? <HomePage profile={profile} wallet={wallet} walletError={walletError} recent={recent} recentBusy={recentBusy} recentError={recentError} activePayment={activePayment}
      onNavigate={navigate} onRetryWallet={() => void refreshWallet()} onRetryRecent={() => void refreshRecent()} onContinue={continuePayment} />
      : route.view === 'history' ? <HistorySection history={historyList} historyBusy={historyBusy} historyError={historyError} page={route.page} busy={busy}
        onRefresh={() => void refreshHistory()} onPageChange={page => navigate(historyHref(page))} onOpenPayment={item => void openPayment(item)} onNavigate={navigate} />
        : <TuitionPage profile={profile} wallet={wallet} walletError={walletError} mssv={mssv} tuition={tuition} terms={terms} payment={displayPayment} activePayment={activePayment} receiptOnly={Boolean(viewedPayment)} otp={otp} seconds={seconds} busy={busy} error={error}
          onMssvChange={value => { lookupGeneration.current += 1; setMssv(value); setTuition(null); setTerms(false); setError(null); }}
          onTermsChange={setTerms} onOtpChange={setOtp} onLookup={lookup} onCreate={createPayment} onConfirm={confirmPayment} onStartAgain={startAgain} onNavigate={navigate}
          onRetryWallet={() => void refreshWallet()} onContinue={continuePayment} />}
  </AppShell>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
