import React from "react";
import { Minus, Square, X } from "lucide-react";

export const WindowControls: React.FC = () => {
  const handleMinimize = () => {
    (window as any).electronAPI?.minimize();
  };
  const handleMaximize = () => {
    (window as any).electronAPI?.maximize();
  };
  const handleClose = () => {
    (window as any).electronAPI?.close();
  };

  return (
    <div className="h-8 flex items-stretch titlebar-no-drag select-none shrink-0">
      <button 
        type="button"
        onClick={handleMinimize} 
        className="w-[46px] h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-gray-100 transition-colors cursor-pointer"
        title="最小化"
      >
        <Minus size={13} strokeWidth={1.5} />
      </button>
      <button 
        type="button"
        onClick={handleMaximize} 
        className="w-[46px] h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-gray-100 transition-colors cursor-pointer"
        title="最大化"
      >
        <Square size={11} strokeWidth={1.5} />
      </button>
      <button 
        type="button"
        onClick={handleClose} 
        className="w-[46px] h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-[#e81123] hover:text-white dark:hover:bg-[#e81123] dark:hover:text-white transition-colors cursor-pointer"
        title="关闭"
      >
        <X size={14} strokeWidth={1.5} />
      </button>
    </div>
  );
};
