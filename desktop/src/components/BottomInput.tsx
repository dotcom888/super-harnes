import React, { useState, useEffect, useRef } from "react";
import { 
  Plus, 
  Zap, 
  FileEdit, 
  Compass, 
  ShieldCheck, 
  Shield, 
  ChevronDown, 
  RotateCw, 
  ArrowUp, 
  ChevronDown as ScrollDown, 
  Check,
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
import { TelemetryMetrics, AttachmentItem } from "../types";
import { PendingAttachmentChip } from "./AttachmentCards";
import { readMediaFromClipboard, extractFilesFromClipboardEvent, saveDraft, loadDraft, clearDraft } from "../utils/clipboardHelper";
import { InputContextMenu, ContextMenuPosition } from "./InputContextMenu";
import { EXECUTION_MODES, normalizeModeId, getModeDisplayName, ExecutionModeId } from "../utils/modeHelper";

interface BottomInputProps {
  onSend: (text: string, model: string, permission: string, attachments?: AttachmentItem[]) => void;
  isLoading: boolean;
  metrics: TelemetryMetrics;
  onScrollToBottom?: () => void;
  showScrollBottom?: boolean;
  models?: string[];
  selectedModel?: string;
  modelProviders?: Record<string, string>;
  onSelectModel?: (m: string) => void;
  onOpenModelSettings?: () => void;
  draftText?: string;
  onDraftConsumed?: () => void;
  onPause?: () => void;
  projectName?: string;
  sessionId?: string;
  permissionMode?: string;
  onPermissionChange?: (newMode: string) => void;
  draftAttachments?: AttachmentItem[];
  onDraftChange?: (text: string, attachments: AttachmentItem[]) => void;
}

interface CommandItem {
  cmd: string;
  name: string;
  desc: string;
  icon: React.ReactNode;
}

export const BottomInput: React.FC<BottomInputProps> = ({
  onSend,
  isLoading,
  metrics,
  onScrollToBottom,
  showScrollBottom = false,
  models = [],
  selectedModel,
  modelProviders,
  onSelectModel,
  onOpenModelSettings,
  draftText,
  onDraftConsumed,
  onPause,
  projectName,
  sessionId,
  permissionMode,
  onPermissionChange,
  draftAttachments,
  onDraftChange
}) => {
  const sessionKey = `${projectName || "default"}:${sessionId || "default"}`;
  const [input, setInput] = useState(() => {
    if (sessionId) {
      const d = loadDraft(sessionKey);
      return d.text || draftText || "";
    }
    return draftText || "";
  });
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [model, setModel] = useState(selectedModel || models[0] || "");
  const [permission, setPermission] = useState(permissionMode || "Auto 模式");

  useEffect(() => {
    if (permissionMode) {
      setPermission(permissionMode);
    }
  }, [permissionMode]);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showPermMenu, setShowPermMenu] = useState(false);
  const [showCommandMenu, setShowCommandMenu] = useState(false);

  // 附件上传与拖拽状态
  const [attachments, setAttachments] = useState<AttachmentItem[]>(() => {
    if (sessionId) {
      const d = loadDraft(sessionKey);
      return d.attachments.length > 0 ? d.attachments : (draftAttachments || []);
    }
    return draftAttachments || [];
  });
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const lastPasteTimeRef = useRef(0);

  // 会话切换与持久草稿隔离绑定：切换会话时，严格加载目标会话草稿，绝不残留其他会话输入
  useEffect(() => {
    if (sessionId) {
      const d = loadDraft(sessionKey);
      setInput(d.text || "");
      setAttachments(d.attachments || []);
    } else {
      setInput("");
      setAttachments([]);
    }
  }, [sessionId, projectName]);

  // 当外部快捷指令注入 draftText 时同步
  useEffect(() => {
    if (draftText) {
      setInput(draftText);
      onDraftConsumed?.();
    }
  }, [draftText]);

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
            if (sessionId) saveDraft(sessionKey, input, nextAtts);
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
        if (sessionId) saveDraft(sessionKey, updated, attachments);
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

    // 2. 检查 Electron 原生 IPC 读取系统真实文件路径 (针对 Windows 资源管理器复制的文件)
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

  // 输入框自适应高度调节：换行时随内容动态扩展，范围扩大至 1.5 倍 (约 144px，舒适容纳约 6~7 行输入)
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const baseHeight = 44; // 基础 2 行高度
    const maxHeight = 144; // 扩大至 1.5 倍 (144px)
    const targetHeight = Math.min(Math.max(textarea.scrollHeight, baseHeight), maxHeight);
    textarea.style.height = `${targetHeight}px`;
  }, [input]);

  useEffect(() => {
    if (selectedModel !== undefined) {
      setModel(selectedModel || "");
    } else if (!model && models.length > 0) {
      setModel(models[0]);
    }
  }, [selectedModel, models]);

  useEffect(() => {
    if (draftText !== undefined && draftText !== "") {
      setInput(draftText);
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
      if (onDraftConsumed) {
        onDraftConsumed();
      }
    }
  }, [draftText, onDraftConsumed]);

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
    },
    {
      cmd: "/status",
      name: "查看系统状态",
      desc: "查看当前工作区路径、大模型配置与 MCP 工具状态",
      icon: <RotateCw size={14} className="text-emerald-500" />
    }
  ];

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
    if (sessionId) {
      clearDraft(sessionKey);
    }
    setInput("");
    setAttachments([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectModel = (m: string) => {
    setModel(m);
    setShowModelMenu(false);
    if (onSelectModel) {
      onSelectModel(m);
    }
  };

  return (
    <div className="w-full bg-white dark:bg-[#0f1117] px-4 pb-2 pt-1 border-t border-gray-100 dark:border-gray-800 select-none relative transition-colors duration-150">
      {/* 悬浮回底箭头按钮 (对标需求 2：不遮挡输入框，往上移至 -top-11，且仅在未处于最底部时显现) */}
      {showScrollBottom && onScrollToBottom && (
        <button
          onClick={onScrollToBottom}
          className="absolute -top-11 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-white dark:bg-[#1e202a] border border-gray-200/90 dark:border-gray-700/80 shadow-md flex items-center justify-center text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition hover:shadow-lg cursor-pointer z-30 animate-in fade-in zoom-in-95 duration-150"
          title="回到底部"
        >
          <ScrollDown size={16} />
        </button>
      )}

      {/* 底部吸附输入框卡片 (支持拖拽与复制粘贴上传) */}
      <div 
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onPaste={handlePaste}
        onContextMenu={handleContextMenu}
        className={`w-full bg-white dark:bg-[#181920] border ${
          isDragging ? "border-blue-500 ring-2 ring-blue-500/20" : "border-gray-200 dark:border-gray-800"
        } shadow-sm focus-within:shadow-md focus-within:border-gray-300 dark:focus-within:border-gray-700 rounded-2xl p-3 transition relative`}
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
                  if (sessionId) saveDraft(sessionKey, input, nextAtts);
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
            if (sessionId) saveDraft(sessionKey, val, attachments);
            onDraftChange?.(val, attachments);
          }}
          onKeyDown={handleKeyDown}
          placeholder={currentModeId === "plan" ? "【Plan 模式 · 方案先行】输入你想规划的任务或重构目标，智能体将先深入调研并输出完整施工方案..." : "给 super 智能体发消息，输入 / 或点击左下角 + 选择快捷指令..."}
          style={{ minHeight: "44px", maxHeight: "144px" }}
          className="w-full resize-none border-none outline-none text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 text-sm leading-relaxed bg-transparent overflow-y-auto"
        />

        {/* 卡片工具条 */}
        <div className="flex items-center justify-between pt-1 mt-1 border-t border-gray-50">
          <div className="flex items-center gap-2 relative">
            {/* 图二标红的 '+' 号：点击弹出快捷命令选择器 */}
            <div className="relative">
              <button 
                type="button" 
                onClick={() => setShowCommandMenu(!showCommandMenu)}
                className={`p-1.5 rounded-lg transition cursor-pointer flex items-center justify-center ${
                  showCommandMenu 
                    ? "bg-blue-100 text-blue-600 font-bold" 
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                }`}
                title="选择快捷指令"
              >
                <Plus size={17} />
              </button>

              {/* 快捷指令弹出菜单 */}
              {showCommandMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-20 cursor-default" 
                    onClick={() => setShowCommandMenu(false)} 
                  />
                  <div className="absolute left-0 bottom-9 w-72 bg-white dark:bg-[#1e202a] border border-gray-200 dark:border-gray-700 shadow-2xl rounded-2xl py-2 z-30 text-xs animate-in fade-in zoom-in-95 duration-100">
                    <div className="px-3.5 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
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

            {/* 权限控制下拉项：对标 Claude Code 4 阶执行模式 */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowPermMenu(!showPermMenu)}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#222534] rounded-lg transition font-medium cursor-pointer"
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
                  <div className="absolute left-0 bottom-8 w-64 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                    <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                      <span>运行安全级别</span>
                      <span className="text-[10px] text-gray-400">4 阶策略</span>
                    </div>
                    {EXECUTION_MODES.map((item) => {
                      const isSelected = currentModeId === item.id;
                      return (
                        <div
                          key={item.id}
                          onClick={() => {
                            setPermission(item.name);
                            setShowPermMenu(false);
                            onPermissionChange?.(item.name);
                          }}
                          className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-[#222534] cursor-pointer flex flex-col transition ${
                            isSelected ? "text-blue-600 font-semibold bg-blue-50/50 dark:bg-blue-950/30" : "text-gray-700 dark:text-gray-300"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {renderModeIcon(item.id)}
                              <span>{item.name}</span>
                            </div>
                            {isSelected && <Check size={13} className="text-blue-600 ml-1 shrink-0" />}
                          </div>
                          <span className="text-[10px] text-gray-400 mt-0.5 leading-tight">{item.desc}</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5 relative">
            {/* 模型选择：未配置模型时按钮为空白，下拉列表底部提供“添加模型” */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowModelMenu(!showModelMenu)}
                className="flex items-center gap-1 text-xs text-gray-700 dark:text-gray-300 font-medium hover:text-blue-600 dark:hover:text-blue-400 px-2 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-[#222534] transition cursor-pointer min-h-[26px]"
              >
                <span>{model || ""}</span>
                <ChevronDown size={11} className="text-gray-400" />
              </button>

              {showModelMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-20 cursor-default" 
                    onClick={() => setShowModelMenu(false)} 
                  />
                  <div className="absolute right-0 bottom-8 w-56 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                    <div className="px-3.5 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
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

            {/* 重试/刷新小按钮 */}
            <button
              type="button"
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#222534] rounded-lg transition cursor-pointer"
              title="刷新/重置会话"
            >
              <RotateCw size={14} />
            </button>

            {/* 蓝色向上发送按钮 / 思考中暂停按钮 (对标需求 2) */}
            {isLoading ? (
              <button
                type="button"
                onClick={onPause}
                className="w-7 h-7 rounded-full flex items-center justify-center transition shadow-sm bg-red-500 hover:bg-red-600 dark:bg-rose-600 dark:hover:bg-rose-700 text-white cursor-pointer animate-pulse shrink-0"
                title="暂停思考与执行"
              >
                <Square size={12} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleSubmit()}
                disabled={!input.trim()}
                className={`w-7 h-7 rounded-full flex items-center justify-center transition shadow-sm shrink-0 ${
                  input.trim()
                    ? "bg-blue-600 hover:bg-blue-700 text-white cursor-pointer"
                    : "bg-blue-200 dark:bg-gray-700 text-white cursor-not-allowed"
                }`}
              >
                <ArrowUp size={15} />
              </button>
            )}
          </div>
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

      {/* 底部遥测状态栏 */}
      <div className="w-full text-center py-1 text-[11px] text-gray-400 dark:text-gray-500 font-mono tracking-tight flex items-center justify-center gap-2">
        <span>{metrics.turns} 轮 · {metrics.steps} 步</span>
        <span>|</span>
        <span>LLM {metrics.total_time} · 工具调用 {metrics.tool_time}</span>
        <span>|</span>
        <span>首 token {metrics.ttft && metrics.ttft !== "--" ? metrics.ttft : "--"} · {metrics.tokens_per_sec} tok/s</span>
        <span>|</span>
        <span>缓存命中 {Math.round(metrics.cache_hit_rate * 100)}%</span>
        <span>|</span>
        <span>输入 {(metrics.prompt_tokens / 1000000).toFixed(1)}M tok · 输出 {(metrics.completion_tokens / 1000).toFixed(1)}k tok</span>
      </div>
    </div>
  );
};
