import React, { useState } from "react";
import { Sparkles, Check, X, MessageSquareQuote } from "lucide-react";
import { UserInputRequest } from "../types";

interface UserInputModalProps {
  request: UserInputRequest | null;
  onSubmit: (requestId: string, selectedOption: string, customInput: string) => void;
  onCancel: (requestId: string) => void;
}

export const UserInputModal: React.FC<UserInputModalProps> = ({ request, onSubmit, onCancel }) => {
  if (!request) return null;

  const [selectedOption, setSelectedOption] = useState<string>(
    request.options && request.options.length > 0 ? request.options[0] : ""
  );
  const [customInput, setCustomInput] = useState<string>("");

  const handleSubmit = () => {
    onSubmit(request.request_id, selectedOption, customInput.trim());
  };

  const handleCancel = () => {
    onCancel(request.request_id);
  };

  const canSubmit = Boolean(selectedOption || customInput.trim());

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-[520px] bg-white dark:bg-[#1a1d28] rounded-2xl shadow-2xl border border-blue-200/80 dark:border-blue-900/60 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* 卡片顶部标题 */}
        <div className="px-5 py-3.5 bg-blue-50/90 dark:bg-[#202538] border-b border-blue-100 dark:border-blue-950/60 flex items-center justify-between text-blue-900 dark:text-blue-300">
          <div className="flex items-center gap-2">
            <Sparkles size={17} className="text-blue-600 dark:text-blue-400" />
            <span className="font-semibold text-sm">
              {request.header || "super 智能体需要您的确认与方案选择"}
            </span>
          </div>
          <button
            type="button"
            onClick={handleCancel}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* 提问与方案选项 */}
        <div className="p-5 text-xs space-y-3.5">
          {/* 提问描述 */}
          <div className="flex items-start gap-2 bg-gray-50/80 dark:bg-[#151722] p-3 rounded-xl border border-gray-100 dark:border-[#222534]">
            <MessageSquareQuote size={16} className="text-blue-500 shrink-0 mt-0.5" />
            <p className="text-gray-800 dark:text-gray-200 font-medium leading-relaxed whitespace-pre-wrap">
              {request.question}
            </p>
          </div>

          {/* 候选方案单选 */}
          {request.options && request.options.length > 0 && (
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 block">
                请选择方案：
              </label>
              <div className="space-y-1.5">
                {request.options.map((opt, idx) => {
                  const isSelected = selectedOption === opt;
                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedOption(opt)}
                      className={`p-2.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                        isSelected
                          ? "bg-blue-50/80 dark:bg-blue-950/30 border-blue-500 dark:border-blue-400 text-blue-900 dark:text-blue-200 font-medium"
                          : "bg-white dark:bg-[#181a24] border-gray-200/80 dark:border-[#252837] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#1f2230]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`w-4 h-4 rounded-full border flex items-center justify-center text-[10px] ${
                          isSelected
                            ? "border-blue-600 bg-blue-600 text-white"
                            : "border-gray-400 text-transparent"
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

          {/* 自定义方案 / 补充说明 */}
          {request.allow_custom !== false && (
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 block">
                或者输入自定义方案 / 补充说明（可选）：
              </label>
              <textarea
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                placeholder="在此输入您的自定义想法、参数或补充要求..."
                rows={3}
                className="w-full p-2.5 rounded-xl border border-gray-200 dark:border-[#2a2e3f] bg-white dark:bg-[#151722] text-xs text-gray-900 dark:text-gray-100 outline-none focus:border-blue-500 dark:focus:border-blue-400 resize-none transition"
              />
            </div>
          )}
        </div>

        {/* 底部操作按钮 */}
        <div className="px-5 py-3 bg-gray-50 dark:bg-[#181a24] border-t border-gray-100 dark:border-[#222534] flex justify-end gap-2 text-xs">
          <button
            type="button"
            onClick={handleCancel}
            className="flex items-center gap-1.5 px-3.5 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl font-medium transition cursor-pointer"
          >
            <X size={13} />
            <span>取消 / 跳过</span>
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl font-medium transition shadow-sm cursor-pointer ${
              canSubmit
                ? "bg-blue-600 hover:bg-blue-700 text-white"
                : "bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed"
            }`}
          >
            <Check size={14} />
            <span>确认方案并继续</span>
          </button>
        </div>
      </div>
    </div>
  );
};
