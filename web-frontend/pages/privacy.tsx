/** WP-72 — the privacy policy. Public; also served by the API at /privacy. */
import { LegalPage } from '@/components/legal/LegalPage';

export default function PrivacyPage() {
  return <LegalPage kind="privacy" />;
}
