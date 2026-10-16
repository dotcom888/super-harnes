import React, { useEffect, useRef } from "react";
import { Copy, Clipboard, CheckSquare } from "lucide-react";

export interface ContextMenuPosition {
  x: number;
  y: number;
}

interface InputContextMenuProps {
  position: ContextMenuPosition | null;
  onClose: () => void;
  onCopy: () => void;
  onPaste: () => void;
  onSelectAll: () => void;
  canCopy?: boolean;
}

export const InputContextMenu: React.FC<InputContextMenuProps> = ({
  position,
  onClose,
  onCopy,
  onPaste,
  onSelectAll,
  canCopy = true
}) => {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!position) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    // 延迟 30ms 绑定，避免唤起右键菜单的同一个鼠标事件触发即时关闭
    const timer = setTimeout(() => {
      window.addEventListener("mousedown", handleClickOutside);
    }, 30);
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", onClose, true);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", onClose, true);
    };
  }, [position, onClose]);

  if (!position) return null;

  // 窗口边界保护：防止右键菜单超出屏幕右侧或下侧边缘
  const menuWidth = 144;
  const menuHeight = 122;
  const x = Math.min(position.x, window.innerWidth - menuWidth - 8);
  const y = Math.min(position.y, window.innerHeight - menuHeight - 8);

  return (
    <div
      ref={menuRef}
      style={{ left: `${Math.max(8, x)}px`, top: `${Math.max(8, y)}px` }}
      className="fixed z-[99999] bg-white/95 dark:bg-[#181a24]/95 border border-gray-200/90 dark:border-gray-700/80 rounded-xl shadow-xl backdrop-blur-md p-1 min-w-[136px] text-xs text-gray-700 dark:text-gray-200 select-none animate-in fade-in zoom-in-95 duration-100"
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={() => {
          onCopy();
          onClose();
        }}
        disabled={!canCopy}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-gray-100/80 dark:hover:bg-[#252834] disabled:opacity-40 disabled:pointer-events-none transition cursor-pointer text-left font-medium"
      >
        <div className="flex items-center gap-2">
          <Copy size={13} className="text-gray-500 dark:text-gray-400" />
          <span>复制</span>
        </div>
        <span className="text-[10px] text-gray-400 font-mono">Ctrl+C</span>
      </button>

      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={() => {
          onPaste();
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-gray-100/80 dark:hover:bg-[#252834] transition cursor-pointer text-left font-medium"
      >
        <div className="flex items-center gap-2">
          <Clipboard size={13} className="text-gray-500 dark:text-gray-400" />
          <span>粘贴</span>
        </div>
        <span className="text-[10px] text-gray-400 font-mono">Ctrl+V</span>
      </button>

      <div className="my-1 border-t border-gray-100 dark:border-gray-800" />

      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={() => {
          onSelectAll();
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-gray-100/80 dark:hover:bg-[#252834] transition cursor-pointer text-left font-medium"
      >
        <div className="flex items-center gap-2">
          <CheckSquare size={13} className="text-gray-500 dark:text-gray-400" />
          <span>全选</span>
        </div>
        <span className="text-[10px] text-gray-400 font-mono">Ctrl+A</span>
      </button>
    </div>
  );
};
