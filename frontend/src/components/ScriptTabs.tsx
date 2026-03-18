import { useAppStore } from '../store/appStore';
import type { ScriptTab } from '../types';

const tabs: { key: ScriptTab; label: string }[] = [
  { key: 'playwright_python', label: 'Playwright (Python)' },
  { key: 'robot_framework', label: 'Robot Framework' },
  { key: 'robot_selenium', label: 'RF + Selenium' },
];

export default function ScriptTabs() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const scripts = useAppStore((s) => s.scripts);

  if (!scripts) return null;

  return (
    <div className="flex border-b border-gray-700 bg-gray-800">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => setActiveTab(tab.key)}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
            activeTab === tab.key
              ? 'border-blue-500 text-blue-400 bg-gray-750'
              : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-600'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
