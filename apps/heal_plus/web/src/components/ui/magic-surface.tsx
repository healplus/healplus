import type { ReactNode } from 'react';

interface MagicBackdropProps {
  className?: string;
}

export function MagicBackdrop({ className = '' }: MagicBackdropProps) {
  return (
    <div aria-hidden="true" className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}>
      <div className="magic-grid-pattern absolute inset-0" />
      <div className="magic-orb magic-orb-primary absolute -left-24 -top-24 h-80 w-80 rounded-full" />
      <div className="magic-orb magic-orb-secondary absolute -right-24 top-1/3 h-96 w-96 rounded-full" />
    </div>
  );
}

export function BorderBeam() {
  return <span aria-hidden="true" className="magic-border-beam" />;
}

interface MarqueeProps {
  items: ReactNode[];
}

export function Marquee({ items }: MarqueeProps) {
  return (
    <div className="magic-marquee" role="list" aria-label="Recursos do Heal+">
      <div className="magic-marquee-track">
        <div className="magic-marquee-group">
          {items.map((item, index) => (
            <div key={`visible-${index}`} role="listitem" className="magic-marquee-item">
              {item}
            </div>
          ))}
        </div>
        <div aria-hidden="true" className="magic-marquee-group">
          {items.map((item, index) => (
            <div key={`duplicate-${index}`} className="magic-marquee-item">
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
