import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function DailyPracticeRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/atelier');
  }, [router]);

  return (
    <div className="min-h-screen bg-[#eee7da] p-8 text-sm font-bold uppercase tracking-[0.12em]">
      Opening Atelier...
    </div>
  );
}
