type PhoneWidth = 'compact' | 'regular' | 'wide';
type PhoneHeight = 'short' | 'regular' | 'tall';

function classifyWidth(width: number): PhoneWidth {
  if (width <= 360) return 'compact';
  if (width <= 430) return 'regular';
  return 'wide';
}

function classifyHeight(height: number): PhoneHeight {
  if (height <= 700) return 'short';
  if (height <= 840) return 'regular';
  return 'tall';
}

function viewportSize() {
  const root = document.documentElement;
  const visual = window.visualViewport;
  const width = Math.round(visual?.width || window.innerWidth || root.clientWidth);
  const height = Math.round(visual?.height || window.innerHeight || root.clientHeight);
  return { width, height };
}

export function installViewportMetrics() {
  if (typeof window === 'undefined') return () => {};

  const root = document.documentElement;
  let raf = 0;

  const update = () => {
    raf = 0;
    const { width, height } = viewportSize();
    root.style.setProperty('--app-viewport-width', `${width}px`);
    root.style.setProperty('--app-viewport-height', `${height}px`);
    root.dataset.viewportKind = width <= 760 ? 'phone' : width <= 1024 ? 'tablet' : 'desktop';
    root.dataset.phoneWidth = classifyWidth(width);
    root.dataset.phoneHeight = classifyHeight(height);
  };

  const schedule = () => {
    if (raf) return;
    raf = window.requestAnimationFrame(update);
  };

  update();
  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  window.visualViewport?.addEventListener('resize', schedule);
  window.visualViewport?.addEventListener('scroll', schedule);

  return () => {
    if (raf) window.cancelAnimationFrame(raf);
    window.removeEventListener('resize', schedule);
    window.removeEventListener('orientationchange', schedule);
    window.visualViewport?.removeEventListener('resize', schedule);
    window.visualViewport?.removeEventListener('scroll', schedule);
  };
}
