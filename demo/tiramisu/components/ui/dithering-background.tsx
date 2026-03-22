'use client';

import { Suspense, lazy, useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

const Dithering = lazy(() =>
  import('@paper-design/shaders-react').then((mod) => ({ default: mod.Dithering }))
);

type DitheringBackgroundProps = { className?: string };

export function DitheringBackground({ className }: DitheringBackgroundProps) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = !mounted || resolvedTheme !== 'light';

  /* Warm-tinted dithering instead of pure B&W */
  const colorBack = isDark ? '#100E0C' : '#FAF8F5';
  const colorFront = isDark ? '#C4A88E' : '#3D2E24';
  const fallbackBg = isDark ? 'bg-[#100E0C]' : 'bg-[#FAF8F5]';

  const centerDim = isDark
    ? 'radial-gradient(ellipse 55% 60% at 50% 50%, rgba(16,14,12,0.78) 0%, transparent 100%)'
    : 'radial-gradient(ellipse 55% 60% at 50% 50%, rgba(250,248,245,0.84) 0%, transparent 100%)';

  return (
    <>
      <div className={cn('pointer-events-none fixed inset-0 -z-10', fallbackBg, className)}>
        <Suspense fallback={null}>
          <div className="size-full opacity-50">
            <Dithering
              colorBack={colorBack}
              colorFront={colorFront}
              shape="warp"
              type="4x4"
              speed={0.3}
              className="size-full"
              minPixelRatio={1}
            />
          </div>
        </Suspense>
      </div>

      {/* Center vignette — dims/brightens where the UI lives */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-0"
        style={{ background: centerDim }}
      />
    </>
  );
}
