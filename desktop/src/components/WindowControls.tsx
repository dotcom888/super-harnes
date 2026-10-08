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
    <div className="flex items-center titlebar-no-drag select-none">
      <button 
        type="button"
        onClick={handleMinimize} 
        className="w-8 h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100 transition rounded cursor-pointer"
        title="最小化"
      >
        <Minus size={14} />
      </button>
      <button 
        type="button"
        onClick={handleMaximize} 
        className="w-8 h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100 transition rounded cursor-pointer"
        title="最大化"
      >
        <Square size={12} />
      </button>
      <button 
        type="button"
        onClick={handleClose} 
        className="w-8 h-8 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-red-500 hover:text-white dark:hover:bg-red-600 dark:hover:text-white transition rounded cursor-pointer"
        title="关闭"
      >
        <X size={15} />
      </button>
    </div>
  );
};
