import React, { useState } from "react";
import { ShieldAlert, Check, X, ShieldCheck, Sparkles, Terminal } from "lucide-react";
import { UserInputRequest } from "../types";

interface InlineApprovalCardProps {
  request: { ticket_id: string; command: string; reason: string };
  onApprove: (ticketId: string, trustSession: boolean) => void;
  onReject: (ticketId: string) => void;
}

export const InlineApprovalCard: React.FC<InlineApprovalCardProps> = ({
  request,
  onApprove,
  onReject
}) => {
  return (
    <div className="border border-blue-200/90 dark:border-blue-900/70 rounded-2xl bg-white dark:bg-[#151924] overflow-hidden shadow-xs my-2.5 animate-in fade-in zoom-in-95 duration-150 text-xs">
      {/* 顶部标题栏：清爽蓝白风格，醒目 ASK 模式徽标与标题 */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-blue-50/75 dark:bg-blue-950/40 border-b border-blue-100 dark:border-blue-900/50 select-none">
        <div className="flex items-center gap-2">
          <span className="bg-blue-600 text-white text-[10.5px] font-bold px-2 py-0.5 rounded-md uppercase flex items-center gap-1 shadow-2xs">
            <ShieldAlert size={12} />
            <span>ASK 模式审批</span>
          </span>
          <span className="font-bold text-xs text-blue-950 dark:text-blue-100">
            敏感终端命令执行审批请求
          </span>
        </div>
        <span className="text-[10px] text-blue-600/80 dark:text-blue-400 font-mono font-medium">
          需人工确认
        </span>
      </div>

      {/* 正文区域：强化字体对比，命令框采用科技感暗蓝底色，清晰展示命令与拦截原因 */}
      <div className="p-3.5 space-y-3 select-text">
        <p className="text-slate-600 dark:text-slate-300 font-medium text-[11.5px] leading-relaxed">
          智能体在当前思考链路中申请执行以下本地 Shell 命令，请审查后决定是否放行：
        </p>

        {/* 待执行命令框 */}
        <div>
          <div className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Terminal size={11} className="text-blue-600 dark:text-blue-400" />
            <span>待执行命令 (COMMAND)</span>
          </div>
          <pre className="p-3 bg-[#0d1527] dark:bg-[#0a0f1d] text-sky-300 dark:text-sky-300 rounded-xl font-mono text-[11.5px] border border-blue-950 whitespace-pre-wrap shadow-inner overflow-x-auto select-text font-semibold">
            {request.command}
          </pre>
        </div>

        {/* 拦截原因 */}
        {request.reason && (
          <div className="bg-blue-50/60 dark:bg-blue-950/25 p-2.5 rounded-xl border border-blue-200/60 dark:border-blue-900/40 text-[11.5px]">
            <div className="text-[10px] font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wider mb-0.5">
              拦截原因 (REASON)
            </div>
            <p className="text-slate-800 dark:text-slate-200 font-medium leading-relaxed">
              {request.reason}
            </p>
          </div>
        )}
      </div>

      {/* 底部操作按钮：蓝白色系统一风格 */}
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-blue-100/70 dark:border-blue-950/60 px-3.5 pb-3 bg-slate-50/60 dark:bg-[#12151f] select-none">
        <button
          type="button"
          onClick={() => onReject(request.ticket_id)}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl font-semibold transition cursor-pointer text-xs"
        >
          <X size={13} />
          <span>拒绝执行</span>
        </button>
        <button
          type="button"
          onClick={() => onApprove(request.ticket_id, false)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl font-bold transition shadow-xs cursor-pointer text-xs"
        >
          <Check size={13} />
          <span>单次批准</span>
        </button>
        <button
          type="button"
          onClick={() => onApprove(request.ticket_id, true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-xl font-bold transition shadow-xs cursor-pointer text-xs"
        >
          <ShieldCheck size={13} />
          <span>信任本会话</span>
        </button>
      </div>
    </div>
  );
};

interface InlineUserInputCardProps {
  request: UserInputRequest;
  onSubmit: (requestId: string, selectedOption: string, customInput: string) => void;
  onCancel: (requestId: string) => void;
}

export const InlineUserInputCard: React.FC<InlineUserInputCardProps> = ({
  request,
  onSubmit,
  onCancel
}) => {
  const [selectedOption, setSelectedOption] = useState<string>(
    request.options && request.options.length > 0 ? request.options[0] : ""
  );
  const [customInput, setCustomInput] = useState<string>("");

  const handleSubmit = () => {
    onSubmit(request.request_id, selectedOption, customInput.trim());
  };

  const canSubmit = Boolean(selectedOption || customInput.trim());

  return (
    <div className="border border-blue-200/90 dark:border-blue-900/70 rounded-2xl bg-white dark:bg-[#151924] overflow-hidden shadow-xs my-2.5 animate-in fade-in zoom-in-95 duration-150 text-xs">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-blue-50/75 dark:bg-blue-950/40 border-b border-blue-100 dark:border-blue-900/50 select-none">
        <div className="flex items-center gap-2">
          <span className="bg-blue-600 text-white text-[10.5px] font-bold px-2 py-0.5 rounded-md uppercase flex items-center gap-1 shadow-2xs">
            <Sparkles size={12} />
            <span>用户决策</span>
          </span>
          <span className="font-bold text-xs text-blue-950 dark:text-blue-100">
            {request.header || "super 智能体需要您的确认与方案选择"}
          </span>
        </div>
        <span className="text-[10px] text-blue-600/80 dark:text-blue-400 font-mono font-medium">
          交互方案决策
        </span>
      </div>

      {/* 提问描述与方案选项 */}
      <div className="p-3.5 space-y-3 select-text">
        <div className="bg-blue-50/50 dark:bg-[#101420] p-3 rounded-xl border border-blue-100 dark:border-blue-900/40">
          <p className="text-slate-900 dark:text-slate-100 font-semibold text-xs leading-relaxed whitespace-pre-wrap">
            {request.question}
          </p>
        </div>

        {/* 候选选项单选 */}
        {request.options && request.options.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
              请选择方案 (OPTIONS)
            </div>
            <div className="space-y-1.5">
              {request.options.map((opt, idx) => {
                const isSelected = selectedOption === opt;
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedOption(opt)}
                    className={`p-2.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                      isSelected
                        ? "bg-blue-50/90 dark:bg-blue-950/50 border-blue-500 dark:border-blue-400 text-blue-900 dark:text-blue-100 font-bold shadow-2xs"
                        : "bg-white dark:bg-[#1a1e2b] border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-medium hover:bg-slate-50 dark:hover:bg-[#202536]"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-4 h-4 rounded-full border flex items-center justify-center text-[10px] ${
                        isSelected
                          ? "border-blue-600 bg-blue-600 text-white font-bold"
                          : "border-slate-400 text-transparent"
                      }`}>
                        ✓
                      </span>
                      <span>{opt}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 自定义补充输入 */}
        {request.allow_custom !== false && (
          <div>
            <div className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-1">
              补充说明 / 自定义方案 (OPTIONAL)
            </div>
            <textarea
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              placeholder="在此输入您的自定义想法、参数或补充要求..."
              rows={2}
              className="w-full p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-[#0f131e] text-xs font-mono text-slate-900 dark:text-slate-100 outline-none focus:border-blue-500 dark:focus:border-blue-400 resize-none transition"
            />
          </div>
        )}
      </div>

      {/* 底部提交按钮 */}
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-blue-100/70 dark:border-blue-950/60 px-3.5 pb-3 bg-slate-50/60 dark:bg-[#12151f] select-none">
        <button
          type="button"
          onClick={() => onCancel(request.request_id)}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl font-semibold transition cursor-pointer text-xs"
        >
          <X size={13} />
          <span>取消 / 跳过</span>
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl font-bold transition shadow-xs cursor-pointer text-xs ${
            canSubmit
              ? "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white"
              : "bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
          }`}
        >
          <Check size={13} />
          <span>确认方案并继续</span>
        </button>
      </div>
    </div>
  );
};
