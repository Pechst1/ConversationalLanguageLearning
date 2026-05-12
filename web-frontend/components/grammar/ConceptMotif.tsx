import React from 'react';

export type MotifPrimitive = Record<string, any>;

export type MotifConcept = {
  category?: string | null;
  external_id?: string | null;
  atelier_blueprint?: Record<string, any> | null;
};

function motifPaint(value?: string | null) {
  const token = String(value || 'ink').toLowerCase();
  if (token === 'none') return 'none';
  if (token === 'paper') return 'var(--paper, #f7f1e6)';
  if (token === 'paper_2' || token === 'paper-2') return 'var(--paper-2, #eee7da)';
  if (token === 'red') return 'var(--red, #e3341c)';
  if (token === 'blue') return 'var(--blue, #1e4597)';
  if (token === 'yellow') return 'var(--yellow, #f1c40f)';
  if (token === 'muted') return 'var(--ink-2, #69645d)';
  return 'currentColor';
}

function arrowHeadPoints(from: any[] = [], to: any[] = []) {
  const x1 = Number(from[0] || 0);
  const y1 = Number(from[1] || 0);
  const x2 = Number(to[0] || 0);
  const y2 = Number(to[1] || 0);
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const size = 5;
  const a = angle + Math.PI * 0.82;
  const b = angle - Math.PI * 0.82;
  return `${x2},${y2} ${x2 + Math.cos(a) * size},${y2 + Math.sin(a) * size} ${x2 + Math.cos(b) * size},${y2 + Math.sin(b) * size}`;
}

function motifLabelPaint(primitive: MotifPrimitive) {
  if (primitive.label_fill) return motifPaint(primitive.label_fill);
  if (primitive.type === 'text') return motifPaint(primitive.fill || 'ink');
  const fill = String(primitive.fill || '').toLowerCase();
  if (fill === 'ink' || fill === 'blue' || fill === 'red') return motifPaint('paper');
  return motifPaint(primitive.stroke || 'ink');
}

function motifLabel(primitive: MotifPrimitive, key: string) {
  const label = primitive.label || primitive.text;
  if (!label) return null;
  const isRect = primitive.type === 'rect';
  const isCircle = primitive.type === 'circle';
  const x = primitive.x ?? (isCircle ? primitive.cx : 0);
  const y = primitive.y ?? (isCircle ? primitive.cy : 0);
  const w = primitive.w ?? 0;
  const h = primitive.h ?? 0;
  const labelX = primitive.label_x ?? (isRect ? Number(x) + Number(w) / 2 : x);
  const labelY = primitive.label_y ?? (isRect ? Number(y) + Number(h) / 2 + 3 : y);
  const align = primitive.align || (isRect || isCircle ? 'middle' : 'start');
  const font = primitive.font === 'serif_italic' ? 'var(--serif, Georgia)' : 'var(--mono, ui-monospace)';
  return (
    <text
      key={key}
      x={labelX}
      y={labelY}
      textAnchor={align}
      fontFamily={font}
      fontStyle={primitive.font === 'serif_italic' ? 'italic' : undefined}
      fontSize={primitive.size || (isRect ? 8 : 8)}
      fill={motifLabelPaint(primitive)}
    >
      {label}
    </text>
  );
}

export function renderMotifPrimitive(primitive: MotifPrimitive, index: number) {
  const strokeWidth = primitive.stroke_width || primitive.strokeWidth || 2;
  const common = { strokeWidth };
  const key = `${primitive.type || 'shape'}-${primitive.role || index}-${index}`;
  if (primitive.type === 'rect') {
    return (
      <g key={key}>
        <rect
          x={primitive.x}
          y={primitive.y}
          width={primitive.w}
          height={primitive.h}
          fill={motifPaint(primitive.fill)}
          stroke={primitive.stroke ? motifPaint(primitive.stroke) : 'none'}
          {...common}
        />
        {motifLabel(primitive, `${key}-label`)}
      </g>
    );
  }
  if (primitive.type === 'circle') {
    return (
      <g key={key}>
        <circle
          cx={primitive.cx}
          cy={primitive.cy}
          r={primitive.r}
          fill={motifPaint(primitive.fill)}
          stroke={primitive.stroke ? motifPaint(primitive.stroke) : 'none'}
          {...common}
        />
        {motifLabel(primitive, `${key}-label`)}
      </g>
    );
  }
  if (primitive.type === 'line') {
    return (
      <g key={key}>
        <line
          x1={primitive.x1}
          y1={primitive.y1}
          x2={primitive.x2}
          y2={primitive.y2}
          stroke={motifPaint(primitive.stroke)}
          {...common}
        />
        {motifLabel({ ...primitive, x: primitive.x1, y: Number(primitive.y1 || 0) - 4 }, `${key}-label`)}
      </g>
    );
  }
  if (primitive.type === 'arrow') {
    const from = primitive.from || [primitive.x1, primitive.y1];
    const to = primitive.to || [primitive.x2, primitive.y2];
    return (
      <g key={key}>
        <line x1={from[0]} y1={from[1]} x2={to[0]} y2={to[1]} stroke={motifPaint(primitive.stroke)} {...common} />
        <polygon points={arrowHeadPoints(from, to)} fill={motifPaint(primitive.stroke)} />
      </g>
    );
  }
  if (primitive.type === 'path') {
    return <path key={key} d={primitive.d} fill={motifPaint(primitive.fill)} stroke={motifPaint(primitive.stroke)} {...common} />;
  }
  if (primitive.type === 'text') {
    return motifLabel(primitive, key);
  }
  return null;
}

export function ConceptMotif({ concept, size = 92, className }: { concept: MotifConcept; size?: number; className?: string }) {
  const motif = concept.atelier_blueprint?.visual_motif;
  const primitives = Array.isArray(motif?.primitives) ? motif.primitives : [];
  if (primitives.length) {
    const width = Number(motif?.canvas?.width || 84);
    const height = Number(motif?.canvas?.height || 84);
    return (
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={motif.accessibility_label || 'Grammar concept motif'}
        className={className}
      >
        {primitives.map((primitive: MotifPrimitive, index: number) => renderMotifPrimitive(primitive, index))}
      </svg>
    );
  }
  return <FallbackConceptMotif concept={concept} size={size} className={className} />;
}

function FallbackConceptMotif({ concept, size, className }: { concept: MotifConcept; size: number; className?: string }) {
  const cat = `${concept.category || ''} ${concept.external_id || ''}`.toLowerCase();
  if (cat.includes('tense')) {
    return (
      <svg width={size} height={size} viewBox="0 0 84 84" className={className} aria-label="Tense contrast motif" role="img">
        <path d="M2 50 Q20 36 40 50 T82 50" fill="none" stroke="var(--blue, #1e4597)" strokeWidth="2" />
        <line x1="50" y1="14" x2="50" y2="74" stroke="currentColor" strokeWidth="3" />
        <circle cx="50" cy="14" r="5" fill="currentColor" />
        <text x="6" y="68" fontFamily="var(--mono, ui-monospace)" fontSize="8" fill="var(--blue, #1e4597)">IMPF.</text>
        <text x="56" y="78" fontFamily="var(--mono, ui-monospace)" fontSize="8" fill="currentColor">P.C.</text>
      </svg>
    );
  }
  if (cat.includes('neg') || cat.includes('article')) {
    return (
      <svg width={size} height={size} viewBox="0 0 84 84" className={className} aria-label="Negation article motif" role="img">
        <text x="42" y="36" textAnchor="middle" fontFamily="var(--serif, Georgia)" fontStyle="italic" fontSize="20" fill="currentColor">verbe</text>
        <line x1="10" y1="20" x2="74" y2="20" stroke="var(--red, #e3341c)" strokeWidth="2" />
        <text x="10" y="16" fontFamily="var(--mono, ui-monospace)" fontSize="8" fill="var(--red, #e3341c)">NE</text>
        <line x1="10" y1="50" x2="74" y2="50" stroke="var(--red, #e3341c)" strokeWidth="2" />
        <text x="58" y="62" fontFamily="var(--mono, ui-monospace)" fontSize="8" fill="var(--red, #e3341c)">PAS</text>
        <rect x="18" y="66" width="18" height="12" fill="currentColor" />
        <text x="27" y="75" textAnchor="middle" fontFamily="var(--mono, ui-monospace)" fontSize="7" fill="var(--paper, #f7f1e6)">DU</text>
        <line x1="39" y1="72" x2="51" y2="72" stroke="currentColor" strokeWidth="2" />
        <polygon points="49,68 57,72 49,76" fill="currentColor" />
        <rect x="58" y="66" width="18" height="12" fill="none" stroke="currentColor" strokeWidth="2" />
        <text x="67" y="75" textAnchor="middle" fontFamily="var(--mono, ui-monospace)" fontSize="7" fill="currentColor">DE</text>
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 84 84" className={className} aria-label="Condition motif" role="img">
      <rect x="2" y="32" width="22" height="20" fill="none" stroke="currentColor" strokeWidth="2" />
      <text x="13" y="46" fontFamily="var(--mono, ui-monospace)" fontSize="9" fill="currentColor" textAnchor="middle">SI</text>
      <line x1="24" y1="42" x2="36" y2="42" stroke="currentColor" strokeWidth="2" />
      <polygon points="34,38 42,42 34,46" fill="currentColor" />
      <rect x="42" y="32" width="22" height="20" fill="currentColor" />
      <text x="53" y="46" fontFamily="var(--mono, ui-monospace)" fontSize="9" fill="var(--paper, #f7f1e6)" textAnchor="middle">PRÉS</text>
      <line x1="64" y1="42" x2="76" y2="42" stroke="currentColor" strokeWidth="2" />
      <polygon points="74,38 82,42 74,46" fill="currentColor" />
      <circle cx="76" cy="20" r="4" fill="var(--blue, #1e4597)" />
    </svg>
  );
}
