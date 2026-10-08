import React, { useEffect } from "react";
import { AlertTriangle, Trash2, X } from "lucide-react";

interface ConfirmModalProps {
  isOpen: boolean;
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title = "操作确认",
  message,
  confirmText = "确定",
  cancelText = "取消",
  danger = true,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") {
        onCancel();
      } else if (e.key === "Enter") {
        onConfirm();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel, onConfirm]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs select-none animate-in fade-in duration-150">
      <div 
        className="w-full max-w-sm bg-white dark:bg-[#161822] rounded-2xl shadow-2xl border border-gray-200/90 dark:border-[#282c3c] overflow-hidden p-5 transition-all animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3.5">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
            danger 
              ? "bg-red-50 dark:bg-[#2b181e] text-red-600 dark:text-red-400" 
              : "bg-blue-50 dark:bg-[#182030] text-blue-600 dark:text-blue-400"
          }`}>
            {danger ? <Trash2 size={20} /> : <AlertTriangle size={20} />}
          </div>

          <div className="flex-1 min-w-0 pt-0.5">
            <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100">
              {title}
            </h3>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1.5 leading-relaxed break-words">
              {message}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2.5 mt-5 pt-3 border-t border-gray-100 dark:border-gray-800/80">
          <button
            type="button"
            onClick={onCancel}
            className="px-3.5 py-1.5 rounded-xl text-xs font-medium text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-[#222534] transition cursor-pointer"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-1.5 rounded-xl text-xs font-medium text-white transition shadow-sm cursor-pointer ${
              danger
                ? "bg-red-600 hover:bg-red-700 active:scale-98"
                : "bg-blue-600 hover:bg-blue-700 active:scale-98"
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
