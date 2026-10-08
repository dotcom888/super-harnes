import React, { useState } from "react";
import { Terminal, FileText, ChevronDown, ChevronRight, AlertCircle, CheckCircle2 } from "lucide-react";
import { ToolAction } from "../types";

interface ActionItemProps {
  action: ToolAction;
  onOpenFile?: (path: string) => void;
}

export const ActionItem: React.FC<ActionItemProps> = ({ action, onOpenFile }) => {
  const [expanded, setExpanded] = useState(false);
  const isError = action.status === "error";

  return (
    <div className="text-xs text-gray-700 my-1 font-mono">
      <div className="flex items-center gap-2 group">
        {/* 错误红点指示器 vs 普通工具图标 (对标图二) */}
        {isError ? (
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0 inline-block" />
        ) : action.display === "Pwsh" ? (
          <span className="p-0.5 rounded border border-gray-300 text-gray-600 bg-gray-50 flex items-center justify-center shrink-0">
            <Terminal size={11} />
          </span>
        ) : (
          <span className="p-0.5 rounded border border-gray-300 text-gray-600 bg-gray-50 flex items-center justify-center shrink-0">
            <FileText size={11} />
          </span>
        )}

        {/* 工具类别 (Pwsh, Read, Grep, Edit) */}
        <span className={`font-semibold shrink-0 ${isError ? "text-red-600" : "text-gray-800"}`}>
          {action.display}
        </span>
        <span className="text-gray-400">·</span>

        {/* 描述与路径 (如果是文件路径，支持蓝色下划线点击) */}
        {action.path ? (
          <span
            onClick={() => onOpenFile && onOpenFile(action.path!)}
            className="text-gray-800 underline hover:text-blue-600 cursor-pointer transition truncate"
            title="点击预览代码"
          >
            {action.desc}
          </span>
        ) : isError ? (
          <span className="text-red-500 truncate">{action.desc}</span>
        ) : (
          <span className="text-gray-600 truncate">{action.desc}</span>
        )}

        {/* 耗时与展开查看输出 */}
        {action.output && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-400 hover:text-gray-600 text-[10px] ml-auto shrink-0 flex items-center gap-0.5"
          >
            {action.elapsed !== undefined && <span>{action.elapsed}s</span>}
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        )}
      </div>

      {/* 展开的实际控制台/代码输出 */}
      {expanded && action.output && (
        <div className="mt-1.5 ml-5 p-2 bg-gray-50 border border-gray-200 rounded-lg text-[11px] text-gray-800 whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed">
          {action.output}
        </div>
      )}
    </div>
  );
};
