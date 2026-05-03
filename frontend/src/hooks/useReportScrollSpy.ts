import { useEffect, useState } from 'react';

interface UseReportScrollSpyOptions {
  /** Whether the observer should be active */
  enabled: boolean;
  /** Array of section keys to observe (used as element IDs) */
  sectionKeys: string[];
  /** Optional extra element IDs to observe */
  extraIds?: string[];
  /** rootMargin for IntersectionObserver */
  rootMargin?: string;
}

export function useReportScrollSpy({
  enabled,
  sectionKeys,
  extraIds = [],
  rootMargin = '-80px 0px -70% 0px',
}: UseReportScrollSpyOptions) {
  const [currentSection, setCurrentSection] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || sectionKeys.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setCurrentSection(entry.target.id);
          }
        });
      },
      { rootMargin, threshold: 0 }
    );

    sectionKeys.forEach((key) => {
      const el = document.getElementById(key);
      if (el) observer.observe(el);
    });

    extraIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
    // 使用 join 避免数组引用变化导致不必要的重创建
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, sectionKeys.join(','), extraIds.join(','), rootMargin]);

  return currentSection;
}
