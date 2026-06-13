import React from 'react';
import { useRouter } from 'next/router';

export default function DashboardRedirect() {
  const router = useRouter();

  React.useEffect(() => {
    router.replace('/atelier');
  }, [router]);

  return null;
}
