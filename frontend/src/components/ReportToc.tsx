import { useState } from 'react';
import { PanelRightClose, List } from 'lucide-react';

export interface TocSection {
  key: string;
  title: string;
  icon: React.ElementType;
}

interface ReportTocProps {
  sections: TocSection[];
  currentSection: string | null;
  onNavigate: (key: string) => void;
  /** Optional extra items shown before main sections */
  extraItems?: TocSection[];
  /** Color theme for active state */
  colorScheme?: 'primary' | 'indigo';
  /** Whether the TOC should render at all */
  visible?: boolean;
}

export function ReportToc({
  sections,
  currentSection,
  onNavigate,
  extraItems = [],
  colorScheme = 'primary',
  visible = true,
}: ReportTocProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (!visible || sections.length === 0) return null;

  const activeBg = colorScheme === 'indigo' ? 'bg-indigo-50' : 'bg-primary-50';
  const activeText = colorScheme === 'indigo' ? 'text-indigo-700' : 'text-primary-700';

  return (
    <div className="hidden xl:block fixed right-6 top-24 z-40">
      {/* TOC panel */}
      <nav
        className={`w-56 transition-all duration-300 ease-in-out ${
          collapsed
            ? 'translate-x-[120%] opacity-0 pointer-events-none'
            : 'translate-x-0 opacity-100'
        }`}
      >
        <div className="bg-white/90 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/80 p-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
          <div className="flex items-center justify-between mb-3 px-2">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              章节目录
            </h4>
            <button
              onClick={() => setCollapsed(true)}
              className="p-1 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              title="收起目录"
            >
              <PanelRightClose className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-0.5">
            {/* Extra items */}
            {extraItems.map((item) => {
              const ItemIcon = item.icon;
              return (
                <button
                  key={item.key}
                  onClick={() => onNavigate(item.key)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-md text-sm transition-colors flex items-center ${
                    currentSection === item.key
                      ? `${activeBg} ${activeText} font-medium`
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                  }`}
                >
                  <ItemIcon className="w-3.5 h-3.5 mr-2 flex-shrink-0" />
                  <span className="truncate">{item.title}</span>
                </button>
              );
            })}
            {/* Main sections */}
            {sections.map((section) => {
              const SectionIcon = section.icon;
              return (
                <button
                  key={section.key}
                  onClick={() => onNavigate(section.key)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-md text-sm transition-colors flex items-center ${
                    currentSection === section.key
                      ? `${activeBg} ${activeText} font-medium`
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                  }`}
                >
                  <SectionIcon className="w-3.5 h-3.5 mr-2 flex-shrink-0" />
                  <span className="truncate">{section.title}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Floating expand button */}
      <button
        onClick={() => setCollapsed(false)}
        className={`absolute right-0 top-0 w-10 h-10 rounded-full bg-white shadow-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-all duration-300 ${
          collapsed
            ? 'opacity-100 scale-100 translate-x-0'
            : 'opacity-0 scale-75 translate-x-4 pointer-events-none'
        }`}
        title="展开目录"
      >
        <List className="w-4 h-4 text-gray-600" />
      </button>
    </div>
  );
}
