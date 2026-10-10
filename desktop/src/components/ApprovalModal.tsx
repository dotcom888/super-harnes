import React from "react";
import { ShieldAlert, Check, X, ShieldCheck, Terminal } from "lucide-react";

interface ApprovalModalProps {
  request: { ticket_id: string; command: string; reason: string } | null;
  onApprove: (ticketId: string, trustSession: boolean) => void;
  onReject: (ticketId: string) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({ request, onApprove, onReject }) => {
  if (!request) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-[520px] bg-white dark:bg-[#151924] rounded-2xl shadow-2xl border border-blue-200 dark:border-blue-900/70 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-5 py-3.5 bg-blue-50/80 dark:bg-blue-950/50 border-b border-blue-100 dark:border-blue-900/50 flex items-center justify-between text-blue-950 dark:text-blue-100 select-none">
          <div className="flex items-center gap-2">
            <span className="bg-blue-600 text-white text-[11px] font-bold px-2 py-0.5 rounded-md uppercase flex items-center gap-1 shadow-2xs">
              <ShieldAlert size={13} />
              <span>ASK 模式审批</span>
            </span>
            <span className="font-bold text-sm">敏感终端命令审批请求</span>
          </div>
          <span className="text-[11px] text-blue-600 dark:text-blue-400 font-mono">需人工确认</span>
        </div>

        <div className="p-5 text-xs space-y-3.5 select-text">
          <p className="text-slate-600 dark:text-slate-300 font-medium leading-relaxed">
            智能体申请在本地环境中执行以下 Shell 命令，请审查后决定是否放行：
          </p>

          <div>
            <div className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <Terminal size={12} className="text-blue-600 dark:text-blue-400" />
              <span>待执行命令 (COMMAND)</span>
            </div>
            <pre className="p-3.5 bg-[#0d1527] dark:bg-[#0a0f1d] text-sky-300 rounded-xl font-mono text-xs border border-blue-950 whitespace-pre-wrap shadow-inner overflow-x-auto select-text font-semibold">
              {request.command}
            </pre>
          </div>

          {request.reason && (
            <div className="bg-blue-50/60 dark:bg-blue-950/25 p-3 rounded-xl border border-blue-200/60 dark:border-blue-900/40 text-xs">
              <div className="text-[10px] font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wider mb-0.5">
                拦截原因 (REASON)
              </div>
              <p className="text-slate-800 dark:text-slate-200 font-medium leading-relaxed">
                {request.reason}
              </p>
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 bg-slate-50/80 dark:bg-[#12151f] border-t border-blue-100/70 dark:border-blue-950/60 flex justify-end gap-2.5 text-xs select-none">
          <button
            onClick={() => onReject(request.ticket_id)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl font-semibold transition cursor-pointer"
          >
            <X size={14} />
            <span>拒绝执行</span>
          </button>
          <button
            onClick={() => onApprove(request.ticket_id, false)}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl font-bold transition shadow-xs cursor-pointer"
          >
            <Check size={14} />
            <span>单次批准</span>
          </button>
          <button
            onClick={() => onApprove(request.ticket_id, true)}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-xl font-bold transition shadow-xs cursor-pointer"
          >
            <ShieldCheck size={14} />
            <span>信任本会话</span>
          </button>
        </div>
      </div>
    </div>
  );
};
