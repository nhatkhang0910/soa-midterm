export type Profile = { id: string; fullName: string; phone: string; email: string };
export type Wallet = { balance: number; reserved: number; available: number; currency: string };
export type Student = { id: string; mssv: string; fullName: string };
export type Tuition = { student: Student; invoice: { id: string; amount: number; currency: string; status: 'UNPAID' | 'RESERVED' | 'PAID' } | null };
export type Payment = { id: string; status: 'PENDING_OTP' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'EXPIRED'; amount: number; currency: string; otpExpiresAt: string; payer: Profile; student: Student; createdAt: string; failureCode: string | null };
export type PaymentHistory = { items: Payment[]; page: number; pageSize: number; total: number };
export type View = 'home' | 'payment' | 'history' | 'login';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string, public requestId?: string) { super(message); }
}

export const money = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
export const date = (value: string) => new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
export const statusText: Record<Payment['status'], string> = { PENDING_OTP: 'Chờ xác thực', PROCESSING: 'Đang xử lý', SUCCEEDED: 'Thành công', FAILED: 'Không thành công', EXPIRED: 'OTP hết hạn' };
export const isPending = (payment: Payment) => payment.status === 'PENDING_OTP' || payment.status === 'PROCESSING';
