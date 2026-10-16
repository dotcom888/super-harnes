import React, { useState, useEffect, useRef } from "react";
import { 
  Folder, 
  Atom, 
  Zap, 
  FileEdit, 
  Compass, 
  ShieldCheck, 
  Plus, 
  Shield, 
  ChevronDown, 
  ArrowUp, 
  Check, 
  FolderPlus,
  MessageSquare,
  Terminal,
  FileSearch,
  CheckCircle2,
  Bug,
  HelpCircle,
  Minimize2,
  Trash2,
  Layers,
  Square,
  Paperclip,
  UploadCloud,
  Loader2
} from "lucide-react";
import { ProjectInfo, AttachmentItem } from "../types";
import { PendingAttachmentChip } from "./AttachmentCards";
import { readMediaFromClipboard, extractFilesFromClipboardEvent, saveDraft, loadDraft, clearDraft } from "../utils/clipboardHelper";
import { InputContextMenu, ContextMenuPosition } from "./InputContextMenu";
import { LOGO_DATA_URI } from "../assets/logoData";
import { EXECUTION_MODES, normalizeModeId, getModeDisplayName, ExecutionModeId } from "../utils/modeHelper";

interface EmptyStateProps {
  projectName: string;
  sessionId?: string;
  projects?: ProjectInfo[];
  modeName?: string;
  onSend: (text: string, model: string, permission: string, attachments?: AttachmentItem[]) => void;
  isLoading: boolean;
  models?: string[];
  selectedModel?: string;
  modelProviders?: Record<string, string>;
  onSelectModel?: (m: string) => void;
  onOpenModelSettings?: () => void;
  onSelectProject?: (name: string) => void;
  onAddWorkspace?: () => void;
  onPause?: () => void;
  onPermissionChange?: (newMode: string) => void;
  draftText?: string;
  draftAttachments?: AttachmentItem[];
  onDraftChange?: (text: string, attachments: AttachmentItem[]) => void;
}

interface CommandItem {
  cmd: string;
  name: string;
  desc: string;
  icon: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  projectName,
  sessionId,
  projects = [],
  modeName = "AUTO 模式",
  onSend,
  isLoading,
  models = [],
  selectedModel,
  modelProviders,
  onSelectModel,
  onOpenModelSettings,
  onSelectProject,
  onAddWorkspace,
  onPause,
  onPermissionChange,
  draftText,
  draftAttachments,
  onDraftChange
}) => {
  const initialDraft = loadDraft("new_session");
  const [input, setInput] = useState(initialDraft.text || draftText || "");
  const lastPasteTimeRef = useRef(0);
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [model, setModel] = useState(selectedModel || models[0] || "");
  const [permission, setPermission] = useState(modeName || "AUTO 模式");

  useEffect(() => {
    if (modeName) setPermission(modeName);
  }, [modeName]);
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showPermMenu, setShowPermMenu] = useState(false);
  const [showCommandMenu, setShowCommandMenu] = useState(false);

  // 附件上传与拖拽状态
  const [attachments, setAttachments] = useState<AttachmentItem[]>(initialDraft.attachments.length > 0 ? initialDraft.attachments : (draftAttachments || []));
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const dragCounter = useRef(0);
  // 草稿实时外部同步与受保护恢复
  useEffect(() => {
    if (draftText !== undefined && draftText !== input) {
      setInput(draftText);
    }
  }, [draftText]);

  useEffect(() => {
    if (draftAttachments !== undefined) {
      setAttachments(draftAttachments);
    }
  }, [draftAttachments]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    const formData = new FormData();
    Array.from(files).forEach((f) => formData.append("files", f));
    if (projectName) formData.append("project", projectName);
    if (sessionId) formData.append("session_id", sessionId);

    try {
      const res = await fetch("http://127.0.0.1:8765/api/attachments/upload", {
        method: "POST",
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        if (data.attachments) {
          setAttachments((prev) => {
            const nextAtts = [...prev, ...data.attachments];
            saveDraft("new_session", input, nextAtts);
            onDraftChange?.(input, nextAtts);
            return nextAtts;
          });
        }
      }
    } catch (err) {
      console.error("上传附件异常:", err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    try {
      e.dataTransfer.dropEffect = "copy";
    } catch {}
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      e.dataTransfer.dropEffect = "copy";
    } catch {}
    if (!isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(e.dataTransfer.files);
    }
  };

  useEffect(() => {
    if (selectedModel !== undefined) {
      setModel(selectedModel || "");
    } else if (!model && models.length > 0) {
      setModel(models[0]);
    }
  }, [selectedModel, models]);

  const shortcutCommands: CommandItem[] = [
    {
      cmd: "/init",
      name: "初始化感知",
      desc: "扫描项目目录结构、技术栈与依赖环境",
      icon: <Layers size={14} className="text-blue-500" />
    },
    {
      cmd: "/review",
      name: "代码走查审查",
      desc: "对指定模块进行架构审查、潜在漏洞与规范体检",
      icon: <FileSearch size={14} className="text-purple-500" />
    },
    {
      cmd: "/test",
      name: "运行项目测试",
      desc: "执行本地自动化测试套件 (pytest/npm test) 并分析结果",
      icon: <CheckCircle2 size={14} className="text-green-500" />
    },
    {
      cmd: "/fix",
      name: "诊断与 Bug 修复",
      desc: "根据报错日志定位根因，应用最小侵入式补丁修复",
      icon: <Bug size={14} className="text-red-500" />
    },
    {
      cmd: "/explain",
      name: "代码原理解析",
      desc: "深入剖析复杂函数或架构实现的底层运作原理",
      icon: <Terminal size={14} className="text-amber-500" />
    },
    {
      cmd: "/compact",
      name: "压缩会话记忆",
      desc: "智能浓缩历史上下文，释放注意力窗口与 token 预算",
      icon: <Minimize2 size={14} className="text-indigo-500" />
    },
    {
      cmd: "/clear",
      name: "清空重置会话",
      desc: "重置当前对话记录，开启全新独立交互轮次",
      icon: <Trash2 size={14} className="text-gray-500" />
    },
    {
      cmd: "/help",
      name: "智能体操作指南",
      desc: "查看 super 智能体的内置能力、快捷指令与工具列表",
      icon: <HelpCircle size={14} className="text-cyan-500" />
    }
  ];


   // 剪贴板复制粘贴上传 (支持 Windows 资源管理器文件 Ctrl+C 复制后在此处 Ctrl+V 粘贴、截图直接粘贴)
  const handlePaste = async (e: React.ClipboardEvent) => {
    const now = Date.now();
    if (now - lastPasteTimeRef.current < 250) {
      return;
    }

    // 1. 同步优先检查 Web 标准 clipboardData 中的文件与 Blob (微信截图、QQ截图、系统截图)
    const filesToUpload = extractFilesFromClipboardEvent(e);
    if (filesToUpload.length > 0) {
      e.preventDefault();
      e.stopPropagation();
      lastPasteTimeRef.current = now;
      await handleUploadFiles(filesToUpload);
      return;
    }

    // 2. 检查 Electron 原生 IPC 读取操作系统真实文件路径 (针对 Windows 资源管理器复制的文件)
    try {
      const mediaFiles = await readMediaFromClipboard();
      if (mediaFiles && mediaFiles.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        lastPasteTimeRef.current = now;
        await handleUploadFiles(mediaFiles);
        return;
      }
    } catch (err) {
      console.warn("readMediaFromClipboard error:", err);
    }
  };

  // 右键菜单交互操作 (复制、粘贴、全选)
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuPos({ x: e.clientX, y: e.clientY });
  };

  const handleMenuCopy = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const selected = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    const toCopy = selected || textarea.value;
    if (toCopy) {
      navigator.clipboard.writeText(toCopy);
    }
  };

  const handleMenuPaste = async () => {
    const textarea = textareaRef.current;

    // 1. 检查操作系统剪贴板文件或图片
    try {
      const mediaFiles = await readMediaFromClipboard();
      if (mediaFiles && mediaFiles.length > 0) {
        await handleUploadFiles(mediaFiles);
        return;
      }
    } catch (err) {}

    // 2. 文本粘贴
    try {
      const text = await navigator.clipboard.readText();
      if (text && textarea) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const current = textarea.value;
        const updated = current.substring(0, start) + text + current.substring(end);
        setInput(updated);
        saveDraft("new_session", updated, attachments);
        onDraftChange?.(updated, attachments);
        setTimeout(() => {
          textarea.selectionStart = textarea.selectionEnd = start + text.length;
          textarea.focus();
        }, 0);
      }
    } catch {
      if (textarea) {
        textarea.focus();
        document.execCommand("paste");
      }
    }
  };

  const handleMenuSelectAll = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.focus();
    textarea.select();
  };

  const handleSelectCommand = (cmd: string) => {
    setInput((prev) => (prev ? `${cmd} ${prev}` : `${cmd} `));
    setShowCommandMenu(false);
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isLoading || isUploading) return;
    onSend(input, model, permission, attachments);
    clearDraft("new_session");
    setInput("");
    setAttachments([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const currentModeId = normalizeModeId(permission);

  const renderModeIcon = (modeId: ExecutionModeId) => {
    switch (modeId) {
      case "plan":
        return <Compass size={13} className="text-amber-500" />;
      case "edit_auto":
        return <FileEdit size={13} className="text-purple-500" />;
      case "manual":
        return <ShieldCheck size={13} className="text-emerald-500" />;
      default:
        return <Zap size={13} className="text-blue-500" />;
    }
  };

  const handleSelectModel = (m: string) => {
    setModel(m);
    setShowModelMenu(false);
    if (onSelectModel) {
      onSelectModel(m);
    }
  };

  const handleSelectProj = (pname: string) => {
    setShowWorkspaceMenu(false);
    if (onSelectProject) {
      onSelectProject(pname);
    }
  };

  const displayProjects = projects;

  return (
    <div className="flex-1 h-full flex flex-col items-center justify-center px-4 bg-white dark:bg-[#0f1117] select-none transition-colors duration-150">
      <div className="w-full max-w-2xl flex flex-col items-center -mt-16">
        {/* super 品牌标识与标题（提取出的透明图形 Logo） */}
        <div className="flex items-center gap-3 mb-7">
          <img 
            src={LOGO_DATA_URI} 
            alt="super logo" 
            className="w-12 h-12 object-contain shrink-0" 
          />
          <div className="flex items-baseline gap-2">
            <h1 className="text-3xl font-extrabold text-gray-900 dark:text-white tracking-tight">super</h1>
            <span className="bg-black text-white text-[11px] font-bold px-2 py-0.5 rounded tracking-wider">HARNESS</span>
          </div>
          <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2.5 py-0.5 rounded-full ml-1">
            桌面智能体
          </span>
        </div>

        {/* 顶部胶囊标签：工作区选择与 AUTO 模式选择 */}
        <div className="w-full flex items-center gap-2 mb-2 px-1 relative">
          {/* 工作区下拉选择胶囊 */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowWorkspaceMenu(!showWorkspaceMenu)}
              className="flex items-center gap-1.5 px-3 py-1 bg-gray-100 dark:bg-[#20222b] hover:bg-gray-200 dark:hover:bg-[#2a2d39] text-gray-700 dark:text-gray-200 rounded-full text-xs cursor-pointer transition font-medium"
              title="切换工作区或添加磁盘项目"
            >
              {projectName === "_general" ? (
                <MessageSquare size={13} className="text-gray-500" />
              ) : (
                <Folder size={13} className="text-blue-600" />
              )}
              <span>
                {projectName === "_general"
                  ? "不在项目中"
                  : (projectName || (displayProjects.length > 0 ? "选择工作区" : "未添加工作区"))}
              </span>
              <ChevronDown size={12} className="text-gray-400" />
            </button>

            {/* 工作区下拉菜单 */}
            {showWorkspaceMenu && (
              <>
                <div 
                  className="fixed inset-0 z-20 cursor-default" 
                  onClick={() => setShowWorkspaceMenu(false)} 
                />
                <div className="absolute left-0 top-8 w-64 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                  <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                    <span>选择目标工作区</span>
                    <span className="text-[10px] text-gray-400">{displayProjects.length} 个项目</span>
                  </div>
                  <div className="max-h-56 overflow-y-auto py-1">
                    {displayProjects.length === 0 ? (
                      <div className="px-3 py-4 text-center text-xs text-gray-400 dark:text-gray-500">
                        暂无已添加的工作区，请点击下方添加
                      </div>
                    ) : (
                      displayProjects.map((p) => {
                      const isCur = p.name === projectName;
                      return (
                        <div
                          key={p.name}
                          onClick={() => handleSelectProj(p.name)}
                          className={`px-3 py-2 hover:bg-gray-50 cursor-pointer flex items-center justify-between transition ${
                            isCur ? "text-blue-600 font-semibold bg-blue-50/60" : "text-gray-700"
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate pr-2">
                            <Folder size={13} className={isCur ? "text-blue-600" : "text-gray-400"} />
                            <span className="truncate">{p.name}</span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <span className="text-[10px] text-gray-400 bg-gray-100 px-1 rounded">
                              {p.session_count || (p.sessions ? p.sessions.length : 0)} 会话
                            </span>
                            {isCur && <Check size={13} className="text-blue-600 ml-1" />}
                          </div>
                        </div>
                      );
                    }))}
                  </div>
                  
                  {/* 下拉框底部操作：添加新的工作区 & 不在项目中 (对标图四需求 5) */}
                  <div className="border-t border-gray-100 dark:border-gray-800 pt-1 mt-1 px-1 space-y-0.5">
                    <button
                      type="button"
                      onClick={() => {
                        setShowWorkspaceMenu(false);
                        if (onAddWorkspace) onAddWorkspace();
                      }}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/30 rounded-lg transition font-medium text-xs text-left cursor-pointer"
                    >
                      <FolderPlus size={14} className="text-blue-600 shrink-0" />
                      <span>+ 添加新的工作区（选择磁盘项目）</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setShowWorkspaceMenu(false);
                        handleSelectProj("_general");
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg transition font-medium text-xs text-left cursor-pointer ${
                        projectName === "_general"
                          ? "text-blue-600 font-semibold bg-blue-50/60 dark:bg-blue-950/40"
                          : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#20232e]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <MessageSquare size={14} className={projectName === "_general" ? "text-blue-600" : "text-gray-400"} />
                        <span>不在项目中</span>
                      </div>
                      {projectName === "_general" && <Check size={13} className="text-blue-600 ml-1" />}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

        </div>

        {/* 右键快捷菜单 */}
        <InputContextMenu
          position={contextMenuPos}
          onClose={() => setContextMenuPos(null)}
          onCopy={handleMenuCopy}
          onPaste={handleMenuPaste}
          onSelectAll={handleMenuSelectAll}
        />

        {/* 悬浮圆角输入框卡片 (支持拖拽上传) */}
        <div 
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onPaste={handlePaste}
          onContextMenu={handleContextMenu}
          className={`w-full bg-white dark:bg-[#161822] border ${
            isDragging ? "border-blue-500 ring-2 ring-blue-500/20" : "border-gray-200 dark:border-[#262a38]"
          } shadow-sm hover:shadow-md focus-within:shadow-md focus-within:border-gray-300 dark:focus-within:border-gray-600 rounded-2xl p-3.5 transition relative`}
        >
          {/* 拖拽感应悬浮蒙层 */}
          {isDragging && (
            <div className="absolute inset-0 bg-blue-50/95 dark:bg-[#161a29]/95 border-2 border-dashed border-blue-500 rounded-2xl flex items-center justify-center gap-2.5 z-40 text-blue-600 dark:text-blue-400 font-medium text-xs backdrop-blur-2xs pointer-events-none select-none">
              <UploadCloud size={20} className="animate-bounce" />
              <span>松开鼠标立即上传文档或图片附件...</span>
            </div>
          )}

          {/* 待发送附件缩略展示栏 */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 pb-2 mb-2 border-b border-gray-100 dark:border-gray-800">
              {attachments.map((att) => (
                <PendingAttachmentChip 
                  key={att.id} 
                  attachment={att} 
                  onRemove={(id) => {
                  setAttachments((prev) => {
                    const nextAtts = prev.filter((a) => a.id !== id);
                    saveDraft("new_session", input, nextAtts);
                    onDraftChange?.(input, nextAtts);
                    return nextAtts;
                  });
                }} 
                />
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onPaste={handlePaste}
            onContextMenu={handleContextMenu}
            onChange={(e) => {
            const val = e.target.value;
            setInput(val);
            saveDraft("new_session", val, attachments);
            onDraftChange?.(val, attachments);
          }}
            onKeyDown={handleKeyDown}
            placeholder={projectName ? `描述你想让 super 智能体在 "${projectName}" 中构建或排查的任务...` : (displayProjects.length > 0 ? "请先在上方选择一个项目工作区，然后输入任务..." : "请先在上方点击添加项目工作区，然后输入任务...")}
            rows={3}
            className="w-full resize-none border-none outline-none text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 text-sm leading-relaxed bg-transparent"
          />

          {/* 卡片底栏工具条 */}
          <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-800 mt-1">
            <div className="flex items-center gap-2 relative">
              {/* '+' 号：点击弹出快捷指令菜单 */}
              <div className="relative">
                <button 
                  type="button" 
                  onClick={() => setShowCommandMenu(!showCommandMenu)}
                  className={`p-1.5 rounded-lg transition cursor-pointer flex items-center justify-center ${
                    showCommandMenu 
                      ? "bg-blue-100 text-blue-600 font-bold" 
                      : "text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20232e]"
                  }`}
                  title="选择快捷指令"
                >
                  <Plus size={18} />
                </button>

                {/* 快捷指令弹出菜单 */}
                {showCommandMenu && (
                  <>
                    <div 
                      className="fixed inset-0 z-20 cursor-default" 
                      onClick={() => setShowCommandMenu(false)} 
                    />
                    <div className="absolute left-0 bottom-9 w-72 bg-white dark:bg-[#1e202a] border border-gray-200 dark:border-gray-700 shadow-2xl rounded-2xl py-2 z-30 text-xs animate-in fade-in zoom-in-95 duration-100">
                      <div className="px-3.5 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 flex items-center justify-between">
                        <span>常用快捷指令</span>
                        <span className="text-[10px] text-gray-400 font-mono">点击直接填入</span>
                      </div>
                      <div className="max-h-64 overflow-y-auto py-1">
                        {shortcutCommands.map((item) => (
                          <div
                            key={item.cmd}
                            onClick={() => handleSelectCommand(item.cmd)}
                            className="px-3 py-2 hover:bg-blue-50/70 cursor-pointer flex items-start gap-2.5 transition text-gray-700 hover:text-blue-900 group"
                          >
                            <div className="mt-0.5 p-1 bg-gray-50 rounded-md group-hover:bg-white group-hover:shadow-xs transition">
                              {item.icon}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-semibold text-blue-600 text-xs">{item.cmd}</span>
                                <span className="font-medium text-gray-900 text-xs">{item.name}</span>
                              </div>
                              <p className="text-[11px] text-gray-400 truncate mt-0.5">{item.desc}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* 新增附件上传按钮 📎 (支持多选与各种文档/图片格式) */}
              <div className="relative">
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  multiple 
                  className="hidden" 
                  onChange={(e) => {
                    if (e.target.files) {
                      handleUploadFiles(e.target.files);
                      e.target.value = "";
                    }
                  }} 
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20232e] transition cursor-pointer flex items-center justify-center"
                  title="添加附件或图片 (支持 txt/md/doc/pdf/excel/图片，亦可直接拖入)"
                >
                  {isUploading ? (
                    <Loader2 size={16} className="text-blue-600 animate-spin" />
                  ) : (
                    <Paperclip size={16} />
                  )}
                </button>
              </div>

              {/* 运行安全模式选择胶囊 (继承 4 阶策略完整切换功能) */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowPermMenu(!showPermMenu)}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-gray-700 dark:text-gray-300 bg-gray-50 hover:bg-gray-100 dark:bg-[#20232e] dark:hover:bg-[#282c3a] rounded-lg border border-gray-200/80 dark:border-gray-800 font-medium transition cursor-pointer"
                  title="切换执行安全模式"
                >
                  {renderModeIcon(currentModeId)}
                  <span>{getModeDisplayName(permission)}</span>
                  <ChevronDown size={11} className="text-gray-400" />
                </button>

                {showPermMenu && (
                  <>
                    <div 
                      className="fixed inset-0 z-20 cursor-default" 
                      onClick={() => setShowPermMenu(false)} 
                    />
                    <div className="absolute left-0 bottom-9 w-64 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                      <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                        <span>运行安全级别</span>
                        <span className="text-[10px] text-gray-400">4 阶策略</span>
                      </div>
                      {EXECUTION_MODES.map((item) => {
                        const isCur = currentModeId === item.id;
                        return (
                          <div
                            key={item.id}
                            onClick={() => {
                              setPermission(item.name);
                              setShowPermMenu(false);
                              onPermissionChange?.(item.name);
                            }}
                            className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-[#222534] cursor-pointer flex flex-col transition ${
                              isCur ? "text-blue-600 dark:text-blue-400 font-semibold bg-blue-50/50 dark:bg-blue-900/20" : "text-gray-700 dark:text-gray-300"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                {renderModeIcon(item.id)}
                                <span>{item.name}</span>
                              </div>
                              {isCur && <Check size={13} className="text-blue-600 dark:text-blue-400" />}
                            </div>
                            <span className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 pl-5">{item.desc}</span>
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 relative">
              {/* 模型选择下拉项：未配置模型时按钮为空白，下拉列表底部提供“添加模型” */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowModelMenu(!showModelMenu)}
                  className="flex items-center gap-1 text-xs text-gray-700 dark:text-gray-300 font-medium hover:text-blue-600 dark:hover:text-blue-400 px-2 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-[#20232e] transition cursor-pointer min-h-[26px]"
                >
                  <span>{model || ""}</span>
                  <ChevronDown size={12} className="text-gray-400" />
                </button>

                {showModelMenu && (
                  <>
                    <div 
                      className="fixed inset-0 z-20 cursor-default" 
                      onClick={() => setShowModelMenu(false)} 
                    />
                    <div className="absolute right-0 bottom-8 w-56 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                      <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                        <span>已配置模型列表</span>
                        <span className="text-[10px] text-gray-400">无缝切换</span>
                      </div>
                      <div className="max-h-56 overflow-y-auto py-1">
                        {models && models.length > 0 ? (
                          models.map((m) => {
                            const isCur = m === model;
                            return (
                              <div
                                key={m}
                                onClick={() => handleSelectModel(m)}
                                className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-[#222534] cursor-pointer flex items-center justify-between transition ${
                                  isCur ? "text-blue-600 font-semibold bg-blue-50/60 dark:bg-blue-900/20" : "text-gray-700 dark:text-gray-300"
                                }`}
                              >
                                <div className="flex flex-col min-w-0 pr-2">
                                  <span className="truncate font-mono">{m}</span>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  {modelProviders && modelProviders[m] && (
                                    <span className="text-[10px] text-gray-400 dark:text-gray-500 font-normal select-none">
                                      {modelProviders[m]}
                                    </span>
                                  )}
                                  {isCur ? (
                                    <Check size={13} className="text-blue-600 dark:text-blue-400 shrink-0" />
                                  ) : (
                                    <span className="w-3.5" />
                                  )}
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="px-3.5 py-3 text-center text-gray-400 text-xs">
                            暂无已配置模型
                          </div>
                        )}
                      </div>
                      <div className="border-t border-gray-100 dark:border-gray-800 p-1">
                        <button
                          type="button"
                          onClick={() => {
                            setShowModelMenu(false);
                            onOpenModelSettings?.();
                          }}
                          className="w-full px-3 py-1.5 hover:bg-blue-50 dark:hover:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg flex items-center justify-center gap-1.5 text-xs font-medium transition cursor-pointer"
                        >
                          <Plus size={13} />
                          <span>添加模型</span>
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* 蓝色向上发送按钮 / 思考中暂停按钮 */}
              {isLoading ? (
                <button
                  type="button"
                  onClick={onPause}
                  className="w-8 h-8 rounded-full flex items-center justify-center transition shadow-sm bg-red-500 hover:bg-red-600 dark:bg-rose-600 dark:hover:bg-rose-700 text-white cursor-pointer animate-pulse shrink-0"
                  title="暂停思考与执行"
                >
                  <Square size={13} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleSubmit()}
                  disabled={!input.trim()}
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition shadow-sm shrink-0 ${
                    input.trim()
                      ? "bg-blue-600 hover:bg-blue-700 text-white cursor-pointer"
                      : "bg-blue-200 dark:bg-gray-700 text-white cursor-not-allowed"
                  }`}
                >
                  <ArrowUp size={16} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
