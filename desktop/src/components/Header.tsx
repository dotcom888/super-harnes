import React from "react";
import { Download, PanelRight } from "lucide-react";

interface HeaderProps {
  sessionTitle: string;
  projectName?: string;
  modeName?: string;
  activeTab: "chat" | "trace";
  onTabChange: (tab: "chat" | "trace") => void;
  onExportLog: () => void;
  isDevToolsOpen?: boolean;
  onToggleDevTools?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  sessionTitle,
  projectName = "super-harnes",
  activeTab,
  onTabChange,
  onExportLog,
  isDevToolsOpen = false,
  onToggleDevTools
}) => {
  return (
    <header className="h-12 border-b border-[#e5e7eb] dark:border-[#20222b] flex items-center justify-between px-5 bg-white dark:bg-[#13151b] select-none titlebar-drag-region shrink-0 relative transition-colors duration-150">
      {/* 1. 左侧：会话标题与所属项目 */}
      <div className="flex items-center gap-2 titlebar-no-drag min-w-0 max-w-[calc(50%-100px)] z-10">
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

      {/* 2. 中部：严格绝对居中的“对话”与“轨迹”选项卡 */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-6 titlebar-no-drag h-full z-10">
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

      {/* 3. 右侧：纯图标按钮组 (导出日志 + 侧边栏开关，去掉冗余文字描述，对标需求 1) */}
      <div className="flex items-center gap-1.5 titlebar-no-drag z-10">
        {/* Session log 导出日志按钮 (纯图标) */}
        <button
          type="button"
          onClick={onExportLog}
          className="p-1.5 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-[#1f2230] border border-gray-200/80 dark:border-[#262a38] rounded-lg transition cursor-pointer"
          title="导出会话日志 (Session log)"
        >
          <Download size={15} />
        </button>

        {/* 调试侧边栏开关按钮 (纯图标，对标需求 1) */}
        {onToggleDevTools && (
          <button
            type="button"
            onClick={onToggleDevTools}
            className={`p-1.5 rounded-lg border transition cursor-pointer ${
              isDevToolsOpen
                ? "bg-blue-50 dark:bg-[#1a2333] border-blue-200 dark:border-blue-800/60 text-blue-600 dark:text-blue-400"
                : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-[#1f2230] border-gray-200/80 dark:border-[#262a38]"
            }`}
            title="调试侧边栏 (内置终端 & 浏览器)"
          >
            <PanelRight size={15} />
          </button>
        )}
      </div>
    </header>
  );
};
