import React from "react";
import { Download } from "lucide-react";
import { WindowControls } from "./WindowControls";

interface HeaderProps {
  sessionTitle: string;
  projectName?: string;
  modeName?: string;
  activeTab: "chat" | "trace";
  onTabChange: (tab: "chat" | "trace") => void;
  onExportLog: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  sessionTitle,
  projectName = "super-harnes",
  activeTab,
  onTabChange,
  onExportLog
}) => {
  return (
    <header className="h-16 border-b border-[#e5e7eb] dark:border-[#20222b] flex items-center justify-between px-5 bg-white dark:bg-[#13151b] select-none titlebar-drag-region shrink-0 relative transition-colors duration-150">
      {/* 1. 左侧：会话标题与项目 (即将到达居中按钮区域时自动以 ... 隐藏截断) */}
      <div className="flex items-center gap-2 titlebar-no-drag min-w-0 max-w-[calc(50%-130px)] z-10">
        <span 
          className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate"
          title={sessionTitle}
        >
          {sessionTitle}
        </span>
        <span className="text-[11px] text-gray-400 dark:text-gray-500 font-mono shrink-0">
          ({projectName})
        </span>
      </div>

      {/* 2. 中部：严格绝对居中的“对话”与“轨迹”选项卡 (对标需求 2) */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-8 titlebar-no-drag h-full z-10">
        <button
          type="button"
          onClick={() => onTabChange("chat")}
          className={`h-full flex items-center text-sm font-medium transition border-b-2 px-2 cursor-pointer ${
            activeTab === "chat"
              ? "border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-500 font-semibold"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          }`}
        >
          对话
        </button>
        <button
          type="button"
          onClick={() => onTabChange("trace")}
          className={`h-full flex items-center text-sm font-medium transition border-b-2 px-2 cursor-pointer ${
            activeTab === "trace"
              ? "border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-500 font-semibold"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          }`}
        >
          轨迹
        </button>
      </div>

      {/* 3. 右侧：Session log 导出与窗口控制按钮 */}
      <div className="flex items-center gap-3 titlebar-no-drag z-10">
        <button
          type="button"
          onClick={onExportLog}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700/80 rounded-lg transition cursor-pointer"
        >
          <span>Session log</span>
          <Download size={13} />
        </button>

        <div className="-mr-2">
          <WindowControls />
        </div>
      </div>
    </header>
  );
};
