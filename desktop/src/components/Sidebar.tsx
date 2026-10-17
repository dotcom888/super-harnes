import React, { useState, useEffect, useRef } from "react";
import { 
  Folder, 
  Plus, 
  FolderPlus, 
  Puzzle, 
  Settings, 
  PanelLeftClose, 
  PanelLeft, 
  ChevronDown,
  ChevronUp, 
  ChevronRight,
  MoreHorizontal,
  Pin,
  PinOff,
  Edit2,
  Trash2,
  X,
  FolderOpen,
  Edit3,
  MessageSquare,
  ArrowRightLeft
} from "lucide-react";
import { SessionInfo, ProjectInfo } from "../types";
import { LOGO_DATA_URI } from "../assets/logoData";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  projectName: string;
  projects?: ProjectInfo[];
  sessions: SessionInfo[];
  recentSessions?: SessionInfo[];
  activeSessionId: string;
  onSelectSession: (id: string, projectName?: string) => void;
  onSelectProject?: (name: string) => void;
  onNewSession: () => void;
  onNewRecentSession?: () => void;
  onAddWorkspace?: () => void;
  onOpenSettings: () => void;
  onOpenPlugins: () => void;
  onEditProject?: (oldName: string, newName: string, path?: string) => void;
  onPinProject?: (name: string, pinned: boolean) => void;
  onDeleteProject?: (name: string) => void;
  onRenameSession?: (project: string, sid: string, newTitle: string) => void;
  onPinSession?: (project: string, sid: string, pinned: boolean) => void;
  onDeleteSession?: (project: string, sid: string) => void;
  onMoveSessionToProject?: (sid: string, fromProj: string, toProj: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  projectName,
  projects = [],
  sessions,
  recentSessions = [],
  activeSessionId,
  onSelectSession,
  onSelectProject,
  onNewSession,
  onNewRecentSession,
  onAddWorkspace,
  onOpenSettings,
  onOpenPlugins,
  onEditProject,
  onPinProject,
  onDeleteProject,
  onRenameSession,
  onPinSession,
  onDeleteSession,
  onMoveSessionToProject
}) => {
  const [isProjectsExpanded, setIsProjectsExpanded] = useState<boolean>(true);
  const [isRecentExpanded, setIsRecentExpanded] = useState<boolean>(true);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});
  const [expandedMoreProjects, setExpandedMoreProjects] = useState<Record<string, boolean>>({});

  // 操作菜单弹出层状态
  const [activeProjectMenu, setActiveProjectMenu] = useState<{ name: string; x: number; y: number } | null>(null);
  const [activeSessionMenu, setActiveSessionMenu] = useState<{ project: string; sid: string; x: number; y: number } | null>(null);

  // 编辑项目工作区弹窗
  const [editingProject, setEditingProject] = useState<{ oldName: string; newName: string; path: string } | null>(null);

  // 重命名会话弹窗
  const [renamingSession, setRenamingSession] = useState<{ project: string; sid: string; title: string } | null>(null);

  const toggleProject = (name: string) => {
    setExpandedProjects((prev) => ({
      ...prev,
      [name]: !(prev[name] ?? (name === projectName))
    }));
  };

  // 选择磁盘目录
  const handleBrowseDir = async () => {
    const electronAPI = (window as any).electronAPI;
    if (electronAPI?.selectDirectory) {
      try {
        const dir = await electronAPI.selectDirectory();
        if (dir && editingProject) {
          setEditingProject({ ...editingProject, path: dir });
        }
      } catch (e) {}
    }
  };

  if (collapsed) {
    return (
      <aside className="w-14 h-full bg-[#f8f9fa] border-r border-[#e5e7eb] flex flex-col items-center py-3 justify-between select-none">
        <div className="flex flex-col items-center gap-4">
          <button 
            onClick={onToggleCollapse} 
            className="p-2 hover:bg-[#e5e7eb] rounded-lg text-gray-600 transition cursor-pointer"
            title="展开侧边栏"
          >
            <PanelLeft size={20} />
          </button>
          <button 
            onClick={onNewSession} 
            className="p-2 bg-white border border-[#e5e7eb] shadow-sm hover:bg-gray-50 rounded-lg text-gray-700 transition cursor-pointer"
            title="新会话"
          >
            <Plus size={18} />
          </button>
        </div>
        <div className="flex flex-col items-center gap-2">
          <button onClick={onOpenPlugins} className="p-2 hover:bg-[#e5e7eb] rounded-lg text-gray-600 transition cursor-pointer" title="插件市场">
            <Puzzle size={18} />
          </button>
          <button onClick={onOpenSettings} className="p-2 hover:bg-[#e5e7eb] rounded-lg text-gray-600 transition cursor-pointer" title="设置">
            <Settings size={18} />
          </button>
        </div>
      </aside>
    );
  }

  const displayProjects = projects;

  return (
    <aside className="w-64 h-full bg-[#f8f9fa] dark:bg-[#13151b] border-r border-[#e5e7eb] dark:border-[#20222b] flex flex-col justify-between select-none shrink-0 relative transition-colors duration-150">
      {/* 顶部 Brand 与 折叠按钮 */}
      <div className="flex flex-col min-h-0 flex-1 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-[#f1f3f5] shrink-0">
          <div className="flex items-center gap-2.5">
            <img 
              src={LOGO_DATA_URI} 
              alt="super logo" 
              className="w-6 h-6 object-contain shrink-0" 
            />
            <span className="font-bold text-[16px] tracking-tight text-gray-900 dark:text-white">super</span>
            <span className="bg-black text-white text-[10px] font-bold px-1.5 py-0.5 rounded tracking-wider">HARNESS</span>
          </div>
          <button 
            onClick={onToggleCollapse} 
            className="text-gray-400 hover:text-gray-700 p-1 hover:bg-[#e5e7eb] rounded transition cursor-pointer"
            title="收起侧边栏"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        {/* 新会话悬浮按钮 */}
        <div className="px-3 py-3 shrink-0">
          <button
            onClick={onNewSession}
            className="w-full flex items-center justify-center gap-2 py-2 bg-white dark:bg-[#1e202a] border border-[#e5e7eb] dark:border-[#2a2d39] hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-[#252835] shadow-sm rounded-xl text-gray-800 dark:text-gray-100 font-medium text-sm transition cursor-pointer"
          >
            <Plus size={16} className="text-gray-600" />
            <span>新会话</span>
          </button>
        </div>

        {/* 工作区多项目目录树（展示全部项目，带置顶与更多操作） */}
        <div className="px-3 pt-1 flex-1 overflow-y-auto">
          <div className="space-y-1">
            <div 
              onClick={() => setIsProjectsExpanded(!isProjectsExpanded)}
              className="flex items-center justify-between px-1.5 py-1 text-xs text-gray-600 dark:text-gray-300 font-semibold rounded-lg hover:bg-gray-100/70 dark:hover:bg-[#1a1d27] transition cursor-pointer"
            >
              <div className="flex items-center gap-1.5 flex-1 min-w-0">
                {isProjectsExpanded ? <ChevronDown size={14} className="text-gray-400 shrink-0" /> : <ChevronRight size={14} className="text-gray-400 shrink-0" />}
                <span className="font-bold">项目</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500 font-normal">
                  ({displayProjects.length})
                </span>
              </div>
              <div className="flex items-center gap-1 text-gray-400 shrink-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onAddWorkspace) onAddWorkspace();
                  }}
                  className="p-1 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-200/60 dark:hover:bg-[#222534] rounded transition cursor-pointer"
                  title="添加工作区 (选择磁盘项目)"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>

          {isProjectsExpanded && (
            <div className="space-y-1 pb-2 pl-0.5 max-h-[50vh] overflow-y-auto pr-1 sidebar-scroll-box">
            {displayProjects.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500 flex flex-col items-center gap-2">
                <FolderPlus size={20} className="text-gray-300 dark:text-gray-600 mb-0.5" />
                <span className="font-medium text-gray-500 dark:text-gray-400">暂无项目工作区</span>
                <span className="text-[11px] text-gray-400 dark:text-gray-500">点击右上角或下方添加</span>
                <button
                  type="button"
                  onClick={onAddWorkspace}
                  className="mt-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/40 dark:hover:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-lg text-xs font-semibold transition cursor-pointer"
                >
                  + 添加工作区
                </button>
              </div>
            ) : (
              displayProjects.map((proj) => {
              const isCurrent = proj.name === projectName;
              const isExpanded = expandedProjects[proj.name] ?? isCurrent;
              const projSessions = proj.sessions || [];
              const isPinned = proj.is_pinned;

              const activeSessionIdx = projSessions.findIndex((s) => s.session_id === activeSessionId);
              const isShowAll = expandedMoreProjects[proj.name] ?? (isCurrent && activeSessionIdx >= 5);
              const shouldShowAll = isShowAll;
              const visibleSessions = shouldShowAll ? projSessions : projSessions.slice(0, 5);

              return (
                <div key={proj.name} className="space-y-0.5 group/proj">
                  {/* 项目文件夹栏 (悬浮显示居中的 '...' 按钮，支持右键操作) */}
                  <div 
                    onClick={() => toggleProject(proj.name)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setActiveProjectMenu({ name: proj.name, x: e.clientX, y: e.clientY });
                    }}
                    className={`flex items-center justify-between px-2 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition relative border ${
                      isCurrent 
                        ? "bg-[#e2e6eb] dark:bg-[#202535] text-gray-900 dark:text-blue-300 border-transparent dark:border-blue-500/20" 
                        : "border-transparent text-gray-700 dark:text-gray-400 hover:bg-[#eceef0] dark:hover:bg-[#181a24] hover:text-gray-900 dark:hover:text-gray-200"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                      {isExpanded ? <ChevronDown size={13} className="text-gray-400 shrink-0" /> : <ChevronRight size={13} className="text-gray-400 shrink-0" />}
                      <Folder size={14} className={isCurrent ? "text-blue-600 shrink-0" : "text-gray-500 shrink-0"} />
                      <span className="truncate">{proj.name}</span>
                      {isPinned && <Pin size={10} className="text-blue-600 shrink-0 rotate-45" />}
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {/* 鼠标悬停显示 '...' 居中操作按钮 */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const rect = e.currentTarget.getBoundingClientRect();
                          setActiveProjectMenu({ name: proj.name, x: rect.right, y: rect.bottom });
                        }}
                        className="opacity-0 group-hover/proj:opacity-100 hover:bg-gray-300/60 p-0.5 rounded text-gray-500 transition cursor-pointer"
                        title="项目操作"
                      >
                        <MoreHorizontal size={14} />
                      </button>

                      <span className="text-[10px] text-gray-400 dark:text-gray-500 font-mono px-1 rounded bg-gray-100 dark:bg-[#1c1f2b] shrink-0">
                        {projSessions.length}
                      </span>
                    </div>
                  </div>

                  {/* 展开后的会话列表项 (对标需求 5：从上向下丝滑摊开/推出，收起时反向向上平滑收拢) */}
                  <div
                    className={`grid transition-all duration-200 ease-out ${
                      isExpanded 
                        ? "grid-rows-[1fr] opacity-100 mt-0.5" 
                        : "grid-rows-[0fr] opacity-0 pointer-events-none"
                    }`}
                  >
                    <div className="overflow-hidden">
                      <div className="pl-4 space-y-0.5 border-l-2 border-gray-200/80 dark:border-gray-800 ml-3 py-0.5">
                        {projSessions.length === 0 ? (
                          <div className="px-2 py-1 text-[11px] text-gray-400 italic">暂无历史消息</div>
                        ) : (
                          <>
                          {visibleSessions.map((s) => {
                            const isActive = isCurrent && s.session_id === activeSessionId;
                            const displayTitle = s.current_goal || (s.session_id === "default" ? "默认会话" : s.session_id);
                            const isSessionPinned = s.is_pinned;

                            return (
                              <div
                                key={`${proj.name}-${s.session_id}`}
                                onClick={() => onSelectSession(s.session_id, proj.name)}
                                onContextMenu={(e) => {
                                  e.preventDefault();
                                  setActiveSessionMenu({ project: proj.name, sid: s.session_id, x: e.clientX, y: e.clientY });
                                }}
                                className={`group/sess flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition relative border ${
                                  isActive
                                    ? "bg-blue-100/80 dark:bg-blue-900/30 text-blue-900 dark:text-blue-300 shadow-xs border-transparent dark:border-blue-700/30"
                                    : "border-transparent text-gray-600 dark:text-gray-400 hover:bg-[#eceef0] dark:hover:bg-[#181a24] hover:text-gray-900 dark:hover:text-gray-200"
                                }`}
                              >
                                <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                                  {isSessionPinned && <Pin size={10} className="text-blue-600 shrink-0 rotate-45" />}
                                  <span className="truncate max-w-[125px]" title={displayTitle}>
                                    {displayTitle}
                                  </span>
                                </div>

                                <div className="flex items-center gap-1 shrink-0">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      const rect = e.currentTarget.getBoundingClientRect();
                                      setActiveSessionMenu({ project: proj.name, sid: s.session_id, x: rect.right, y: rect.bottom });
                                    }}
                                    className="opacity-0 group-hover/sess:opacity-100 hover:bg-gray-300/60 p-0.5 rounded text-gray-500 transition cursor-pointer"
                                    title="会话操作"
                                  >
                                    <MoreHorizontal size={14} />
                                  </button>
                                  <span className="text-[10px] text-gray-400 shrink-0">
                                    {s.time_ago || "历史"}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                          {projSessions.length > 5 && (
                            shouldShowAll ? (
                              <button
                                type="button"
                                onClick={() => setExpandedMoreProjects((prev) => ({ ...prev, [proj.name]: false }))}
                                className="w-full flex items-center gap-1 px-2.5 py-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100/60 dark:hover:bg-[#181a24] rounded-md transition cursor-pointer mt-0.5"
                              >
                                <ChevronUp size={12} />
                                <span>收起</span>
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => setExpandedMoreProjects((prev) => ({ ...prev, [proj.name]: true }))}
                                className="w-full flex items-center justify-between px-2.5 py-1 text-[11px] text-blue-600 dark:text-blue-400 hover:bg-blue-50/60 dark:hover:bg-blue-900/20 rounded-md transition font-medium cursor-pointer mt-0.5"
                              >
                                <span className="flex items-center gap-1">
                                  <ChevronDown size={12} />
                                  <span>展开显示</span>
                                </span>
                                <span className="text-[10px] text-gray-400">还有 {projSessions.length - 5} 项</span>
                              </button>
                            )
                          )}
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            }))}
          </div>
          )}
          </div>

          {/* ================= 2. 下半部分：最近 ∨ (带 ... 和 编辑图标，对标图三) ================= */}
          <div className="space-y-1 border-t border-gray-200/60 dark:border-[#1e222f] pt-2.5">
            <div 
              onClick={() => setIsRecentExpanded(!isRecentExpanded)}
              className="flex items-center justify-between px-1.5 py-1 text-xs text-gray-600 dark:text-gray-300 font-semibold rounded-lg hover:bg-gray-100/70 dark:hover:bg-[#1a1d27] transition cursor-pointer"
            >
              <div className="flex items-center gap-1.5 flex-1 min-w-0">
                {isRecentExpanded ? <ChevronDown size={14} className="text-gray-400 shrink-0" /> : <ChevronRight size={14} className="text-gray-400 shrink-0" />}
                <span className="font-bold">最近</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500 font-normal">
                  ({recentSessions.length})
                </span>
              </div>
              <div className="flex items-center gap-1 text-gray-400 shrink-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onNewRecentSession) {
                      onNewRecentSession();
                    } else {
                      onNewSession();
                    }
                  }}
                  className="p-1 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-200/60 dark:hover:bg-[#222534] rounded transition cursor-pointer"
                  title="新建独立对话"
                >
                  <Edit3 size={13} />
                </button>
              </div>
            </div>

            {isRecentExpanded && (
              <div className="space-y-0.5 pl-0.5 pb-2">
                {recentSessions.length === 0 ? (
                  <div className="px-3 py-2 text-center text-xs text-gray-400 dark:text-gray-500 italic">
                    暂无独立对话
                  </div>
                ) : (
                  recentSessions.map((s) => {
                    const isRecentActive = (projectName === "" || projectName === "_general") && s.session_id === activeSessionId;
                    const displayTitle = s.current_goal || (s.session_id === "default" ? "独立对话" : s.session_id);
                    const isSessionPinned = s.is_pinned;

                    return (
                      <div
                        key={"recent-" + s.session_id}
                        onClick={() => onSelectSession(s.session_id, "_general")}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          setActiveSessionMenu({ project: "_general", sid: s.session_id, x: e.clientX, y: e.clientY });
                        }}
                        className={"group/recent flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition relative " + (
                          isRecentActive
                            ? "bg-blue-100/80 dark:bg-blue-900/40 text-blue-900 dark:text-blue-200 shadow-2xs"
                            : "text-gray-600 dark:text-gray-400 hover:bg-[#eceef0] dark:hover:bg-[#181a24] hover:text-gray-900 dark:hover:text-gray-200"
                        )}
                      >
                        <div className="flex items-center gap-1.5 truncate flex-1 min-w-0 pr-1">
                          <MessageSquare size={13} className={isRecentActive ? "text-blue-600 shrink-0" : "text-gray-400 shrink-0"} />
                          {isSessionPinned && <Pin size={10} className="text-blue-600 shrink-0 rotate-45" />}
                          <span className="truncate max-w-[130px]" title={displayTitle}>
                            {displayTitle}
                          </span>
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const rect = e.currentTarget.getBoundingClientRect();
                              setActiveSessionMenu({ project: "_general", sid: s.session_id, x: rect.right, y: rect.bottom });
                            }}
                            className="opacity-0 group-hover/recent:opacity-100 hover:bg-gray-300/60 dark:hover:bg-[#282d3e] p-0.5 rounded text-gray-500 transition cursor-pointer"
                            title="会话操作"
                          >
                            <MoreHorizontal size={14} />
                          </button>
                          <span className="text-[10px] text-gray-400 shrink-0">
                            {s.time_ago || "历史"}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 底部功能区：插件市场与设置 */}
      <div className="p-3 border-t border-[#f1f3f5] dark:border-[#1e222f] space-y-0.5 shrink-0 bg-[#f8f9fa] dark:bg-[#10121a]">
        <button
          onClick={onOpenPlugins}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-gray-700 dark:text-gray-300 hover:bg-[#eceef0] dark:hover:bg-[#181a24] transition font-medium cursor-pointer"
        >
          <Puzzle size={16} className="text-gray-500 dark:text-gray-400" />
          <span>插件市场</span>
        </button>
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-gray-700 dark:text-gray-300 hover:bg-[#eceef0] dark:hover:bg-[#181a24] transition font-medium cursor-pointer"
        >
          <Settings size={16} className="text-gray-500 dark:text-gray-400" />
          <span>设置</span>
        </button>
      </div>

      {/* 1. 项目工作区操作下拉菜单 */}
      {activeProjectMenu && (
        <>
          <div 
            className="fixed inset-0 z-40 cursor-default" 
            onClick={() => setActiveProjectMenu(null)} 
          />
          <div 
            style={{ top: Math.min(activeProjectMenu.y, window.innerHeight - 150), left: Math.min(activeProjectMenu.x, window.innerWidth - 180) }}
            className="fixed z-50 w-44 bg-white dark:bg-[#181a24] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 text-xs select-none animate-in fade-in duration-100 text-gray-700 dark:text-gray-200"
          >
            <button
              onClick={() => {
                const targetP = displayProjects.find((p) => p.name === activeProjectMenu.name);
                setEditingProject({
                  oldName: activeProjectMenu.name,
                  newName: activeProjectMenu.name,
                  path: targetP?.path || ""
                });
                setActiveProjectMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 dark:hover:bg-[#222534] text-gray-700 dark:text-gray-200 text-left transition cursor-pointer"
            >
              <Edit2 size={13} className="text-gray-500" />
              <span>编辑</span>
            </button>

            <button
              onClick={() => {
                const targetP = displayProjects.find((p) => p.name === activeProjectMenu.name);
                if (onPinProject) onPinProject(activeProjectMenu.name, !targetP?.is_pinned);
                setActiveProjectMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 dark:hover:bg-[#222534] text-gray-700 dark:text-gray-200 text-left transition cursor-pointer"
            >
              {displayProjects.find((p) => p.name === activeProjectMenu.name)?.is_pinned ? (
                <>
                  <PinOff size={13} className="text-gray-500" />
                  <span>取消置顶</span>
                </>
              ) : (
                <>
                  <Pin size={13} className="text-blue-600" />
                  <span>置顶</span>
                </>
              )}
            </button>

            <div className="border-t border-gray-100 dark:border-gray-800 dark:border-gray-800 my-0.5" />

            <button
              onClick={() => {
                if (onDeleteProject) onDeleteProject(activeProjectMenu.name);
                setActiveProjectMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-red-50 dark:hover:bg-red-950/30 text-red-600 dark:text-red-400 text-left transition cursor-pointer"
            >
              <Trash2 size={13} />
              <span>删除</span>
            </button>
          </div>
        </>
      )}

      {/* 2. 会话操作下拉菜单 */}
      {activeSessionMenu && (
        <>
          <div 
            className="fixed inset-0 z-40 cursor-default" 
            onClick={() => setActiveSessionMenu(null)} 
          />
          <div 
            style={{ top: Math.min(activeSessionMenu.y, window.innerHeight - 150), left: Math.min(activeSessionMenu.x, window.innerWidth - 180) }}
            className="fixed z-50 w-40 bg-white dark:bg-[#181a24] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 text-xs select-none animate-in fade-in duration-100 text-gray-700 dark:text-gray-200"
          >
            <button
              onClick={() => {
                const proj = displayProjects.find((p) => p.name === activeSessionMenu.project);
                const sess = proj?.sessions.find((s) => s.session_id === activeSessionMenu.sid);
                setRenamingSession({
                  project: activeSessionMenu.project,
                  sid: activeSessionMenu.sid,
                  title: sess?.current_goal || activeSessionMenu.sid
                });
                setActiveSessionMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 dark:hover:bg-[#222534] text-gray-700 dark:text-gray-200 text-left transition cursor-pointer"
            >
              <Edit2 size={13} className="text-gray-500" />
              <span>重命名</span>
            </button>

            <button
              onClick={() => {
                const proj = displayProjects.find((p) => p.name === activeSessionMenu.project);
                const sess = proj?.sessions.find((s) => s.session_id === activeSessionMenu.sid);
                if (onPinSession) onPinSession(activeSessionMenu.project, activeSessionMenu.sid, !sess?.is_pinned);
                setActiveSessionMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 dark:hover:bg-[#222534] text-gray-700 dark:text-gray-200 text-left transition cursor-pointer"
            >
              {(activeSessionMenu.project === "_general" ? recentSessions : displayProjects.find((p) => p.name === activeSessionMenu.project)?.sessions || []).find((s) => s.session_id === activeSessionMenu.sid)?.is_pinned ? (
                <>
                  <PinOff size={13} className="text-gray-500" />
                  <span>取消置顶</span>
                </>
              ) : (
                <>
                  <Pin size={13} className="text-blue-600" />
                  <span>置顶</span>
                </>
              )}
            </button>

            <div className="border-t border-gray-100 dark:border-gray-800 dark:border-gray-800 my-0.5" />

            <button
              onClick={() => {
                if (onDeleteSession) onDeleteSession(activeSessionMenu.project, activeSessionMenu.sid);
                setActiveSessionMenu(null);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-red-50 dark:hover:bg-red-950/30 text-red-600 dark:text-red-400 text-left transition cursor-pointer"
            >
              <Trash2 size={13} />
              <span>删除会话</span>
            </button>
          </div>
        </>
      )}

      {/* 3. 编辑项目工作区弹窗 (更改命名与磁盘目录) */}
      {editingProject && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-96 bg-white dark:bg-[#141620] rounded-2xl shadow-2xl border border-gray-200 dark:border-[#262a38] overflow-hidden p-5 space-y-4 text-xs animate-in fade-in zoom-in-95 duration-150 text-gray-800 dark:text-gray-100">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <span className="font-bold text-gray-900 dark:text-white text-sm">编辑项目工作区</span>
              <button onClick={() => setEditingProject(null)} className="text-gray-400 hover:text-gray-700 cursor-pointer">
                <X size={16} />
              </button>
            </div>

            <div>
              <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">工作区命名</label>
              <input
                type="text"
                value={editingProject.newName}
                onChange={(e) => setEditingProject({ ...editingProject, newName: e.target.value })}
                className="w-full px-3 py-2 bg-white dark:bg-[#1c1f2b] border border-gray-200 dark:border-[#2a2e3f] text-gray-900 dark:text-gray-100 rounded-xl focus:border-blue-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">磁盘对应目录</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editingProject.path}
                  onChange={(e) => setEditingProject({ ...editingProject, path: e.target.value })}
                  placeholder="本地绝对路径"
                  className="flex-1 px-3 py-2 bg-white dark:bg-[#1c1f2b] border border-gray-200 dark:border-[#2a2e3f] text-gray-900 dark:text-gray-100 rounded-xl focus:border-blue-500 outline-none truncate font-mono text-[11px]"
                />
                <button
                  type="button"
                  onClick={handleBrowseDir}
                  className="p-2 border border-gray-200 hover:bg-gray-100 rounded-xl transition cursor-pointer text-gray-600"
                  title="浏览选择文件夹"
                >
                  <FolderOpen size={16} />
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setEditingProject(null)}
                className="px-3 py-1.5 border border-gray-200 hover:bg-gray-100 rounded-xl transition cursor-pointer text-gray-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => {
                  if (onEditProject) {
                    onEditProject(editingProject.oldName, editingProject.newName, editingProject.path);
                  }
                  setEditingProject(null);
                }}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition cursor-pointer shadow-xs"
              >
                保存修改
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. 重命名会话弹窗 */}
      {renamingSession && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-80 bg-white dark:bg-[#141620] rounded-2xl shadow-2xl border border-gray-200 dark:border-[#262a38] overflow-hidden p-5 space-y-4 text-xs animate-in fade-in zoom-in-95 duration-150 text-gray-800 dark:text-gray-100">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <span className="font-bold text-gray-900 dark:text-white text-sm">重命名会话</span>
              <button onClick={() => setRenamingSession(null)} className="text-gray-400 hover:text-gray-700 cursor-pointer">
                <X size={16} />
              </button>
            </div>

            <div>
              <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">会话标题</label>
              <input
                type="text"
                value={renamingSession.title}
                onChange={(e) => setRenamingSession({ ...renamingSession, title: e.target.value })}
                className="w-full px-3 py-2 bg-white dark:bg-[#1c1f2b] border border-gray-200 dark:border-[#2a2e3f] text-gray-900 dark:text-gray-100 rounded-xl focus:border-blue-500 outline-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setRenamingSession(null)}
                className="px-3 py-1.5 border border-gray-200 hover:bg-gray-100 rounded-xl transition cursor-pointer text-gray-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => {
                  if (onRenameSession) {
                    onRenameSession(renamingSession.project, renamingSession.sid, renamingSession.title);
                  }
                  setRenamingSession(null);
                }}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition cursor-pointer shadow-xs"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
