import React, { useState, useEffect, useRef } from "react";
import {
  Terminal as TerminalIcon,
  Globe,
  Plus,
  X,
  ArrowLeft,
  ArrowRight,
  RotateCw,
  ExternalLink,
  MoreHorizontal,
  Maximize2,
  Minimize2,
  PanelRightClose
} from "lucide-react";

export interface DevTab {
  id: string;
  type: "browser" | "terminal";
  title: string;
  url?: string;
}

interface DevToolsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  workspacePath?: string;
  sessionKey: string;
  tabs: DevTab[];
  onTabsChange: (tabs: DevTab[]) => void;
  activeTabId: string | null;
  onActiveTabChange: (id: string | null) => void;
  terminalOutputs: Record<string, string[]>;
  onTerminalOutputsChange: (outputs: Record<string, string[]>) => void;
  isMaximized: boolean;
  onToggleMaximize: (max: boolean) => void;
}

export const DevToolsSidebar: React.FC<DevToolsSidebarProps> = ({
  isOpen,
  onClose,
  workspacePath = "",
  sessionKey,
  tabs,
  onTabsChange,
  activeTabId,
  onActiveTabChange,
  terminalOutputs,
  onTerminalOutputsChange,
  isMaximized,
  onToggleMaximize
}) => {
  // 默认最小宽度常量 (对标需求 1: 默认最小宽度 380px)
  const DEFAULT_MIN_WIDTH = 380;

  // 宽度拖拽调整状态
  const [sidebarWidth, setSidebarWidth] = useState<number>(DEFAULT_MIN_WIDTH);
  const [isResizing, setIsResizing] = useState<boolean>(false);

  // 当处于放大状态后关闭或退出放大态，下次打开重置为默认最小宽度 (对标需求 1 & 图二)
  useEffect(() => {
    if (isMaximized) {
      setSidebarWidth(DEFAULT_MIN_WIDTH);
    }
  }, [isMaximized]);

  useEffect(() => {
    if (!isOpen) {
      setSidebarWidth(DEFAULT_MIN_WIDTH);
    }
  }, [isOpen]);

  // 窗口尺寸变化响应 (对标需求 2 & 图一：窗口恢复/缩小时防止侧边栏挤爆对话区)
  useEffect(() => {
    const handleWindowResize = () => {
      const availableWorkspaceWidth = Math.max(window.innerWidth - 240, 1);
      const maxAllowedWidth = Math.floor(availableWorkspaceWidth * 0.65);
      if (!isMaximized) {
        setSidebarWidth((prev) => {
          if (prev > maxAllowedWidth) {
            return Math.max(DEFAULT_MIN_WIDTH, maxAllowedWidth);
          }
          return prev;
        });
      }
    };

    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, [isMaximized]);

  // "+" 选项弹出菜单 (对标需求 3 & 图三)
  const [showAddMenu, setShowAddMenu] = useState<boolean>(false);
  const addMenuRef = useRef<HTMLDivElement>(null);

  // 浏览器导航状态
  const [urlInput, setUrlInput] = useState("");
  const [showQuickLinks, setShowQuickLinks] = useState(false);
  const webviewRef = useRef<any>(null);

  // 终端状态 (对标需求 5: 消除重复 PS 提示)
  const [terminalInput, setTerminalInput] = useState("");
  const [historyCmds, setHistoryCmds] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);
  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const terminalInputRef = useRef<HTMLInputElement>(null);

  // 初始终端输出信息 (仅保留版权说明，绝不预设多余 PS 提示，对标需求 5)
  const defaultTerminalHeader = [
    "Windows PowerShell",
    "版权所有 (C) Microsoft Corporation。保留所有权利。",
    "",
    "尝试新的跨平台 PowerShell https://aka.ms/pscore6",
    ""
  ];

  // 1. 鼠标自由拖动宽度，并在达到临界值时自动触发最大化 (对标需求 4)
  const handleStartResize = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    if (!isResizing) return;

    let rafId: number | null = null;

    const handleMouseMove = (e: MouseEvent) => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }

      rafId = requestAnimationFrame(() => {
        const clientX = e.clientX;
        const newWidth = window.innerWidth - clientX;

        const availableWorkspaceWidth = Math.max(window.innerWidth - 240, 1);
        const ratio = newWidth / availableWorkspaceWidth;

        // 临界值判定：往左拉占用对话框页面的约 70% 临界值时，直接触发放大 (对标需求 1)
        if (ratio >= 0.70) {
          onToggleMaximize(true);
          setSidebarWidth(DEFAULT_MIN_WIDTH);
          setIsResizing(false);
          return;
        }

        // 正常平滑拖动限制在 [DEFAULT_MIN_WIDTH, availableWorkspaceWidth * 0.69]
        const maxAllowed = Math.floor(availableWorkspaceWidth * 0.69);
        const clampedWidth = Math.max(DEFAULT_MIN_WIDTH, Math.min(maxAllowed, newWidth));
        setSidebarWidth(clampedWidth);
        if (isMaximized) onToggleMaximize(false);
      });
    };

    const handleMouseUp = () => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      setIsResizing(false);
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, isMaximized, onToggleMaximize]);

  // 点击外部关闭 "+" 弹出的下拉菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    if (showAddMenu) {
      window.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showAddMenu]);

  // 创建标签页 (对标需求 3: 下拉框选择添加)
  const handleCreateTab = (type: "browser" | "terminal", initialUrl?: string) => {
    setShowAddMenu(false);
    const id = `tab_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const newTab: DevTab = {
      id,
      type,
      title: type === "browser" ? "New tab" : "PowerShell",
      url: initialUrl || (type === "browser" ? "" : undefined)
    };

    const updatedTabs = [...tabs, newTab];
    onTabsChange(updatedTabs);
    onActiveTabChange(id);

    if (type === "browser") {
      setUrlInput(initialUrl || "");
    } else {
      onTerminalOutputsChange({
        ...terminalOutputs,
        [id]: [...defaultTerminalHeader]
      });

      if ((window as any).electronAPI?.terminalCreate) {
        (window as any).electronAPI.terminalCreate({ id, cwd: workspacePath }).catch(() => {});
        (window as any).electronAPI.onTerminalData?.(id, (chunk: string) => {
          onTerminalOutputsChange({
            ...terminalOutputs,
            [id]: [...(terminalOutputs[id] || defaultTerminalHeader), chunk]
          });
        });
      }
    }
  };

  // 关闭标签页
  const handleCloseTab = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const tabToClose = tabs.find((t) => t.id === id);
    if (tabToClose?.type === "terminal") {
      (window as any).electronAPI?.terminalKill?.({ id });
    }

    const filtered = tabs.filter((t) => t.id !== id);
    onTabsChange(filtered);
    if (activeTabId === id) {
      onActiveTabChange(filtered.length > 0 ? filtered[filtered.length - 1].id : null);
    }
  };

  const activeTab = tabs.find((t) => t.id === activeTabId);

  // 终端命令执行与历史维护
  const handleExecuteTerminalCommand = () => {
    if (!activeTabId) return;
    const cmd = terminalInput.trim();

    if (!cmd) {
      onTerminalOutputsChange({
        ...terminalOutputs,
        [activeTabId]: [...(terminalOutputs[activeTabId] || defaultTerminalHeader), `PS ${workspacePath}>`]
      });
      setTerminalInput("");
      return;
    }

    setHistoryCmds((prev) => [cmd, ...prev.filter((c) => c !== cmd)]);
    setHistoryIndex(-1);

    if (cmd.toLowerCase() === "cls" || cmd.toLowerCase() === "clear") {
      onTerminalOutputsChange({
        ...terminalOutputs,
        [activeTabId]: []
      });
      setTerminalInput("");
      return;
    }

    const promptLine = `PS ${workspacePath}> ${cmd}`;

    if ((window as any).electronAPI?.terminalWrite) {
      onTerminalOutputsChange({
        ...terminalOutputs,
        [activeTabId]: [...(terminalOutputs[activeTabId] || defaultTerminalHeader), promptLine]
      });
      (window as any).electronAPI.terminalWrite({ id: activeTabId, data: cmd + "\r\n" });
    } else {
      onTerminalOutputsChange({
        ...terminalOutputs,
        [activeTabId]: [
          ...(terminalOutputs[activeTabId] || defaultTerminalHeader),
          promptLine,
          `[PowerShell 执行完成: ${cmd}]`
        ]
      });
    }
    setTerminalInput("");
  };

  const handleTerminalKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleExecuteTerminalCommand();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (historyCmds.length > 0 && historyIndex < historyCmds.length - 1) {
        const nextIdx = historyIndex + 1;
        setHistoryIndex(nextIdx);
        setTerminalInput(historyCmds[nextIdx]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex > 0) {
        const nextIdx = historyIndex - 1;
        setHistoryIndex(nextIdx);
        setTerminalInput(historyCmds[nextIdx]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setTerminalInput("");
      }
    }
  };

  useEffect(() => {
    if (activeTab?.type === "terminal") {
      if (terminalContainerRef.current) {
        terminalContainerRef.current.scrollTop = terminalContainerRef.current.scrollHeight;
      }
      terminalInputRef.current?.focus();
    }
  }, [terminalOutputs, activeTabId]);

  // 浏览器导航操作
  const handleNavigate = (targetUrl?: string) => {
    const raw = (targetUrl ?? urlInput).trim();
    if (!raw) return;

    let finalUrl = raw;
    if (!/^https?:\/\//i.test(finalUrl)) {
      if (/^(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/i.test(finalUrl)) {
        finalUrl = `http://${finalUrl}`;
      } else if (finalUrl.includes(".") && !finalUrl.includes(" ")) {
        finalUrl = `https://${finalUrl}`;
      } else {
        finalUrl = `https://cn.bing.com/search?q=${encodeURIComponent(finalUrl)}`;
      }
    }

    setUrlInput(finalUrl);
    const updated = tabs.map((t) => {
      if (t.id === activeTabId) {
        return { ...t, url: finalUrl, title: finalUrl.replace(/^https?:\/\//, "").slice(0, 18) };
      }
      return t;
    });
    onTabsChange(updated);
  };

  const handleOpenExternal = () => {
    const target = urlInput || activeTab?.url;
    if (target) {
      if ((window as any).electronAPI?.openExternal) {
        (window as any).electronAPI.openExternal(target);
      } else {
        window.open(target, "_blank");
      }
    }
  };

  if (!isOpen) return null;

  // 过滤掉输出历史中可能因子进程返回的多余末尾空 PS 提示，确保行内输入前只有一个唯一的 PS (对标需求 5)
  const currentOutputs = terminalOutputs[activeTabId || ""] || defaultTerminalHeader;
  const filteredOutputs = currentOutputs.filter((line, i) => {
    if (i === currentOutputs.length - 1 && /^PS\s+.*>$/i.test(line.trim())) {
      return false;
    }
    return true;
  });

  return (
    <>
      {/* 拖动时的全屏防穿透半透明手柄遮罩 */}
      {isResizing && (
        <div className="fixed inset-0 z-50 cursor-col-resize select-none bg-transparent" />
      )}
      <aside
        style={!isMaximized ? { width: `${sidebarWidth}px`, maxWidth: "calc(100% - 380px)" } : undefined}
        className={`h-full border-l border-gray-200 dark:border-[#20222b] bg-white dark:bg-[#13151b] flex flex-col shrink-0 select-text ${
          isResizing ? "transition-none select-none" : "transition-all duration-150"
        } z-30 ${isMaximized ? "absolute inset-0 w-full" : "relative"}`}
      >
      {/* 0. 左右宽度拖拽手柄 (最大化时不显示拖动手柄) */}
      {!isMaximized && (
        <div
          onMouseDown={handleStartResize}
          className="absolute -left-1 top-0 bottom-0 w-2 cursor-col-resize hover:bg-blue-500/50 active:bg-blue-600 transition-colors z-40"
          title="向左拖动至临界值自动全屏覆盖"
        />
      )}

      {/* 1. 顶栏：标签页栏 / 位于第二行 (对标图二 & 图三) */}
      <div className="h-12 bg-gray-50/90 dark:bg-[#181a24] border-b border-gray-200 dark:border-[#20222b] flex items-center justify-between px-3 select-none shrink-0 titlebar-drag-region">
        {/* 标签栏列表与 "+" 新增下拉菜单 */}
        <div className="flex items-center flex-1 mr-2 titlebar-no-drag min-w-0">
          <div className="flex items-center gap-1 overflow-x-auto no-scrollbar max-w-[calc(100%-48px)]">
            {tabs.map((tab) => {
              const isActive = tab.id === activeTabId;
              return (
                <div
                  key={tab.id}
                  onClick={() => {
                    onActiveTabChange(tab.id);
                    if (tab.type === "browser") setUrlInput(tab.url || "");
                  }}
                  className={`group flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t-lg cursor-pointer transition max-w-[160px] border-b-2 shrink-0 ${
                    isActive
                      ? "bg-white dark:bg-[#13151b] text-gray-900 dark:text-white font-medium border-blue-600 dark:border-blue-500 shadow-2xs"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border-transparent hover:bg-gray-100 dark:hover:bg-[#20222b]"
                  }`}
                >
                  {tab.type === "browser" ? (
                    <Globe size={13} className="shrink-0 text-gray-400" />
                  ) : (
                    <TerminalIcon size={13} className="shrink-0 text-gray-400" />
                  )}
                  <span className="truncate">{tab.title}</span>
                  <button
                    type="button"
                    onClick={(e) => handleCloseTab(tab.id, e)}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-500 rounded p-0.5 ml-1 transition"
                    title="关闭"
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })}
          </div>

          {/* "+" 按钮与下拉选择框 (放置于滚动容器外部，绝不被裁剪，对标需求 3 & 图三) */}
          <div className="relative shrink-0 ml-1.5 z-50" ref={addMenuRef}>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowAddMenu(!showAddMenu);
              }}
              className="p-1.5 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-200/70 dark:hover:bg-[#242735] rounded-md transition cursor-pointer"
              title="新建窗口"
            >
              <Plus size={14} />
            </button>

            {/* 下拉选择弹出层 (对标图三) */}
            {showAddMenu && (
              <div className="absolute left-0 top-9 w-36 bg-white dark:bg-[#1c1f2b] border border-gray-200 dark:border-[#2b3042] rounded-xl shadow-xl p-1.5 z-[100] text-xs select-none">
                <button
                  type="button"
                  onClick={() => handleCreateTab("terminal")}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#252837] transition cursor-pointer"
                >
                  <TerminalIcon size={14} className="text-gray-500 dark:text-gray-400" />
                  <span>Terminal</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleCreateTab("browser")}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#252837] transition cursor-pointer"
                >
                  <Globe size={14} className="text-gray-500 dark:text-gray-400" />
                  <span>Browser</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 右侧控制：最大化/全屏覆盖 ⤢ 与关闭 ◫ (对标需求 4) */}
        <div className="flex items-center gap-1 shrink-0 titlebar-no-drag">
          <button
            type="button"
            onClick={() => onToggleMaximize(!isMaximized)}
            className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/60 dark:hover:bg-[#242735] rounded-lg transition cursor-pointer"
            title={isMaximized ? "缩小还原窗口" : "完全覆盖聊天页面"}
          >
            {isMaximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button
            type="button"
            onClick={() => {
              onToggleMaximize(false);
              onClose();
            }}
            className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-200/60 dark:hover:bg-[#242735] rounded-lg transition cursor-pointer"
            title="关闭侧边栏"
          >
            <PanelRightClose size={14} />
          </button>
        </div>
      </div>

      {/* 2. 主体区：空白入口 / 浏览器模式 / 终端模式 */}
      {tabs.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center select-none bg-white dark:bg-[#13151b]">
          <div className="flex flex-col gap-3.5 w-52">
            <button
              type="button"
              onClick={() => handleCreateTab("terminal")}
              className="flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-[#262a38] bg-gray-50/60 dark:bg-[#181a24] hover:bg-gray-100 dark:hover:bg-[#20222f] hover:border-blue-500/50 text-gray-700 dark:text-gray-200 text-sm font-medium transition shadow-2xs group cursor-pointer"
            >
              <TerminalIcon size={18} className="text-gray-400 group-hover:text-blue-500 transition" />
              <span>Terminal</span>
            </button>
            <button
              type="button"
              onClick={() => handleCreateTab("browser")}
              className="flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-[#262a38] bg-gray-50/60 dark:bg-[#181a24] hover:bg-gray-100 dark:hover:bg-[#20222f] hover:border-blue-500/50 text-gray-700 dark:text-gray-200 text-sm font-medium transition shadow-2xs group cursor-pointer"
            >
              <Globe size={18} className="text-gray-400 group-hover:text-blue-500 transition" />
              <span>Browser</span>
            </button>
          </div>
        </div>
      ) : activeTab?.type === "browser" ? (
        <div className="flex-1 flex flex-col min-h-0 bg-white dark:bg-[#13151b]">
          {/* 浏览器导航条 */}
          <div className="h-10 px-3 border-b border-gray-200 dark:border-[#20222b] flex items-center gap-2 bg-white dark:bg-[#13151b] shrink-0">
            <button
              type="button"
              onClick={() => webviewRef.current?.goBack?.()}
              className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20222b] rounded transition"
              title="后退"
            >
              <ArrowLeft size={14} />
            </button>
            <button
              type="button"
              onClick={() => webviewRef.current?.goForward?.()}
              className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20222b] rounded transition"
              title="前进"
            >
              <ArrowRight size={14} />
            </button>
            <button
              type="button"
              onClick={() => {
                if (webviewRef.current?.reload) webviewRef.current.reload();
                else handleNavigate();
              }}
              className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20222b] rounded transition"
              title="刷新"
            >
              <RotateCw size={13} />
            </button>

            <div className="flex-1 flex items-center relative">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleNavigate();
                }}
                placeholder="Search or enter a URL"
                className="w-full h-7 pl-3 pr-7 bg-gray-100/80 dark:bg-[#1c1f2b] border border-gray-200 dark:border-[#2b3042] rounded-lg text-xs text-gray-800 dark:text-gray-200 outline-none focus:border-blue-500 transition"
              />
              <button
                type="button"
                onClick={() => handleNavigate()}
                className="absolute right-1.5 text-gray-400 hover:text-blue-500 transition cursor-pointer"
                title="前往"
              >
                <ExternalLink size={12} />
              </button>
            </div>

            <div className="relative">
              <button
                type="button"
                onClick={() => setShowQuickLinks(!showQuickLinks)}
                className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20222b] rounded transition cursor-pointer"
                title="快捷网址 / 选项"
              >
                <MoreHorizontal size={14} />
              </button>

              {showQuickLinks && (
                <div className="absolute right-0 top-8 w-48 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] rounded-xl shadow-lg p-2 z-30 text-xs">
                  <div className="px-2 py-1 text-[11px] font-semibold text-gray-400">本地调试端口</div>
                  <button
                    type="button"
                    onClick={() => { handleNavigate("http://localhost:5173"); setShowQuickLinks(false); }}
                    className="w-full text-left px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-[#222534] rounded text-gray-700 dark:text-gray-300 transition"
                  >
                    localhost:5173 (桌面开发前端)
                  </button>
                  <button
                    type="button"
                    onClick={() => { handleNavigate("http://127.0.0.1:8765/api/status"); setShowQuickLinks(false); }}
                    className="w-full text-left px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-[#222534] rounded text-gray-700 dark:text-gray-300 transition"
                  >
                    127.0.0.1:8765 (后端状态)
                  </button>
                  <button
                    type="button"
                    onClick={() => { handleNavigate("http://localhost:3000"); setShowQuickLinks(false); }}
                    className="w-full text-left px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-[#222534] rounded text-gray-700 dark:text-gray-300 transition"
                  >
                    localhost:3000 (本地 Web 服务)
                  </button>
                  <div className="h-px bg-gray-100 dark:bg-[#242735] my-1" />
                  <button
                    type="button"
                    onClick={() => { handleOpenExternal(); setShowQuickLinks(false); }}
                    className="w-full text-left px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-[#222534] rounded text-blue-600 dark:text-blue-400 transition"
                  >
                    在默认外部浏览器中打开
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 relative overflow-hidden bg-white dark:bg-[#0f1117]">
            {activeTab.url ? (
              <iframe
                ref={webviewRef}
                src={activeTab.url}
                className="w-full h-full border-none bg-white"
                title="Mini Browser"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center select-none text-gray-300 dark:text-gray-600">
                <Globe size={64} strokeWidth={1.2} className="mb-4 text-gray-300 dark:text-gray-600" />
                <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">在上方输入 URL 或搜索关键词开始浏览</p>
                <div className="flex flex-wrap gap-2 justify-center max-w-xs">
                  {["http://localhost:5173", "http://127.0.0.1:8765/api/status", "https://cn.bing.com"].map((quick) => (
                    <button
                      key={quick}
                      type="button"
                      onClick={() => handleNavigate(quick)}
                      className="px-2.5 py-1 text-[11px] bg-gray-100 dark:bg-[#1a1d27] hover:bg-gray-200 dark:hover:bg-[#222634] text-gray-600 dark:text-gray-300 rounded-lg border border-gray-200/60 dark:border-[#2a2e3f] transition cursor-pointer"
                    >
                      {quick.replace(/^https?:\/\//, "")}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* 终端视图 (行内交互，消除多余 PS 提示，对标需求 5) */
        <div
          ref={terminalContainerRef}
          onClick={() => terminalInputRef.current?.focus()}
          className="flex-1 p-4 overflow-y-auto font-mono text-xs text-gray-900 dark:text-gray-100 bg-white dark:bg-[#0c0d12] select-text cursor-text leading-relaxed"
        >
          {filteredOutputs.map((line, idx) => (
            <div key={idx} className="whitespace-pre-wrap">
              {line}
            </div>
          ))}

          {/* 唯一的活跃行内交互提示符 */}
          <div className="flex items-center flex-wrap pt-0.5">
            <span className="text-gray-900 dark:text-gray-100 font-bold mr-1.5 select-none shrink-0">
              PS {workspacePath}&gt;
            </span>
            <input
              ref={terminalInputRef}
              type="text"
              value={terminalInput}
              onChange={(e) => setTerminalInput(e.target.value)}
              onKeyDown={handleTerminalKeyDown}
              className="flex-1 min-w-[200px] bg-transparent border-none outline-none font-mono text-xs text-gray-900 dark:text-gray-100 p-0 m-0 caret-blue-500"
              autoFocus
            />
          </div>
        </div>
      )}
    </aside>
    </>
  );
};
