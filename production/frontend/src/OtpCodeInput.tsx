import { useLayoutEffect, useRef, useState } from 'react';

interface OtpCodeInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  invalid: boolean;
  describedBy: string;
}

export function OtpCodeInput({ value, onChange, disabled, invalid, describedBy }: OtpCodeInputProps) {
  const input = useRef<HTMLInputElement>(null);
  const cells = useRef<HTMLDivElement>(null);
  const pendingCaret = useRef<number | null>(null);
  const restoreFocus = useRef(false);
  const [focused, setFocused] = useState(false);
  const [selection, setSelection] = useState({ start: 0, end: 0 });

  function readSelection() {
    setSelection({ start: input.current?.selectionStart ?? 0, end: input.current?.selectionEnd ?? 0 });
  }

  function change(next: string, caret: number) {
    pendingCaret.current = caret;
    onChange(next);
    if (next === value) {
      input.current?.setSelectionRange(caret, caret);
      pendingCaret.current = null;
    }
    setSelection({ start: caret, end: caret });
  }

  useLayoutEffect(() => {
    if (pendingCaret.current === null) return;
    input.current?.setSelectionRange(pendingCaret.current, pendingCaret.current);
    pendingCaret.current = null;
  }, [value]);

  useLayoutEffect(() => {
    if (!disabled && restoreFocus.current && document.activeElement === document.body) input.current?.focus();
  }, [disabled]);

  return <div className="otp-code" data-invalid={invalid || undefined} data-disabled={disabled || undefined}>
    <div className="otp-cells" ref={cells} aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => <span key={index} className="otp-cell"
        data-active={focused && !disabled && index === Math.min(selection.start, 5) || undefined}
        data-selected={focused && !disabled && index >= selection.start && index < selection.end || undefined}
      >{value[index] || ''}</span>)}
    </div>
    {/* One native field keeps paste, autofill and keyboard editing accessible. */}
    <input ref={input} id="otp" className="otp-native-input" type="text" inputMode="numeric"
      autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required
      value={value} disabled={disabled} aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onFocus={() => { restoreFocus.current = true; setFocused(true); readSelection(); }}
      onBlur={event => { if (!event.currentTarget.disabled) restoreFocus.current = false; setFocused(false); }} onSelect={readSelection}
      onChange={event => {
        const raw = event.currentTarget.value;
        const caret = raw.slice(0, event.currentTarget.selectionStart ?? raw.length).replace(/\D/g, '').length;
        change(raw.replace(/\D/g, '').slice(0, 6), caret);
      }}
      onPaste={event => {
        event.preventDefault();
        const digits = event.clipboardData.getData('text').replace(/\D/g, '');
        if (!digits) return;
        if (digits.length >= 6) { change(digits.slice(0, 6), 6); return; }
        const start = event.currentTarget.selectionStart ?? value.length;
        const end = event.currentTarget.selectionEnd ?? start;
        const inserted = digits.slice(0, 6 - value.length + end - start);
        change(value.slice(0, start) + inserted + value.slice(end), start + inserted.length);
      }}
      onPointerDown={event => {
        if (event.button !== 0 || disabled || !cells.current || window.matchMedia('(forced-colors: active)').matches) return;
        const boxes = Array.from(cells.current.children);
        const nearest = boxes.reduce((best, cell, index) => {
          const box = cell.getBoundingClientRect();
          const distance = Math.abs(event.clientX - box.left - box.width / 2);
          return distance < best.distance ? { index, distance } : best;
        }, { index: 0, distance: Infinity }).index;
        event.preventDefault();
        event.currentTarget.focus();
        const start = Math.min(nearest, value.length);
        event.currentTarget.setSelectionRange(start, Math.min(start + 1, value.length));
        readSelection();
      }} />
  </div>;
}
