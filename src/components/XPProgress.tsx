import React, { useEffect, useRef, useState } from "react";

interface XPProgressProps {
  totalXP: number;
  goalXP?: number;
}

export const XPProgress: React.FC<XPProgressProps> = ({ totalXP, goalXP = 100 }) => {
  const [displayXP, setDisplayXP] = useState(0);
  const previousXP = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") {
      setDisplayXP(totalXP);
      previousXP.current = totalXP;
      return;
    }

    let animationFrame: number;
    const start = previousXP.current;
    const diff = totalXP - start;
    const duration = 600;
    const startTime = performance.now();

    const tick = (now: number) => {
      const progress = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayXP(Math.round(start + diff * eased));
      if (progress < 1) {
        animationFrame = requestAnimationFrame(tick);
      } else {
        previousXP.current = totalXP;
      }
    };

    animationFrame = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(animationFrame);
  }, [totalXP]);

  const percent = Math.min(100, (displayXP / goalXP) * 100);

  return (
    <div className="xp-progress">
      <div className="xp-progress__header">
        <span className="xp-progress__label">XP</span>
        <span className="xp-progress__value">{displayXP} / {goalXP}</span>
      </div>
      <div className="xp-progress__bar">
        <div className="xp-progress__fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
};

export default XPProgress;
