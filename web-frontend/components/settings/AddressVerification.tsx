/**
 * S4 stage 3 — the six-digit code that confirms an address, typed in Réglages.
 *
 * Shown while the account's own address is unverified (after sign-up) or while
 * an email change waits for the code sent to the new address. The learner can
 * play meanwhile; only a reset by mail and an email change wait for this.
 */
import React from 'react';
import toast from 'react-hot-toast';

import { Action } from '@/components/atelier-v2/ui';
import type { SettingsCopy } from '@/lib/settings-copy';
import api from '@/services/api';

type Props = {
  copy: SettingsCopy;
  email: string;
  pendingEmail: string | null;
  /** Called with the server's answer once the code was right. */
  onVerified: (result: { email: string; changed: boolean }) => void;
};

export function AddressVerification({ copy, email, pendingEmail, onVerified }: Props) {
  const [code, setCode] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const target = pendingEmail || email;
  const hint = (pendingEmail ? copy.verify_pending_hint : copy.verify_hint).replace('{email}', target);

  const verify = async () => {
    setBusy(true);
    try {
      const result = await api.verifyEmail(code.trim());
      setCode('');
      onVerified({ email: result.email, changed: Boolean(pendingEmail) });
    } catch {
      toast.error(copy.verify_failed);
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setBusy(true);
    try {
      await api.resendEmailVerification();
      toast.success(copy.verify_resent);
    } catch {
      toast.error(copy.verify_failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="st-form" data-address-verification={pendingEmail ? 'change' : 'signup'}>
      <p className="st-row__hint">{hint}</p>
      {!pendingEmail && <p className="st-row__hint">{copy.verify_why}</p>}
      <label className="av2-field">
        <span className="av2-label">{copy.field_code}</span>
        <input
          className="av2-field__control"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
        />
      </label>
      <Action tone="secondary" inline onClick={verify} disabled={busy || code.length !== 6}>
        {copy.action_verify}
      </Action>
      <Action tone="quiet" inline onClick={resend} disabled={busy}>
        {copy.action_resend}
      </Action>
    </div>
  );
}

export default AddressVerification;
