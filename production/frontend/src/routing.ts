import type { View } from './models';

export type Route = { view: View; page: number; href: string; returnTo: string };
export const historyHref = (page = 1) => `/tuition?view=history&page=${page}`;

function tuitionHref(params: URLSearchParams) {
  if (params.get('view') !== 'history') return '/tuition';
  const value = Number(params.get('page'));
  return historyHref(Number.isSafeInteger(value) && value > 0 ? value : 1);
}

export function safeDestination(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/';
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return '/';
    if ([...url.searchParams.keys()].some(key => key !== 'view' && key !== 'page')) return '/';
    if (url.pathname === '/tuition' || url.pathname === '/tuition/') return tuitionHref(url.searchParams);
    if (url.pathname === '/') return url.searchParams.get('view') === 'history' ? tuitionHref(url.searchParams) : '/';
  } catch { /* An invalid return address always falls back to the overview. */ }
  return '/';
}

export function resolveRoute(value = window.location.href): Route {
  const url = new URL(value, window.location.origin);
  if (url.pathname === '/login' || url.pathname === '/login/') {
    const returnTo = safeDestination(url.searchParams.get('next'));
    return { view: 'login', page: 1, href: `/login${returnTo === '/' ? '' : `?next=${encodeURIComponent(returnTo)}`}`, returnTo };
  }
  const href = safeDestination(url.pathname + url.search);
  const params = new URL(href, window.location.origin).searchParams;
  const view = href === '/' ? 'home' : params.get('view') === 'history' ? 'history' : 'payment';
  return { view, page: view === 'history' ? Number(params.get('page')) : 1, href, returnTo: '/' };
}

export function guardRoute(route: Route, authenticated: boolean): Route {
  if (authenticated) return route.view === 'login' ? resolveRoute(route.returnTo) : route;
  return route.view === 'login' ? route : resolveRoute(`/login${route.href === '/' ? '' : `?next=${encodeURIComponent(route.href)}`}`);
}
