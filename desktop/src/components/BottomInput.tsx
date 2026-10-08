import React, { useState, useEffect, useRef } from "react";
import { 
  Plus, 
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
  Square
} from "lucide-react";
import { TelemetryMetrics } from "../types";

interface BottomInputProps {
  onSend: (text: string, model: string, permission: string) => void;
  isLoading: boolean;
  metrics: TelemetryMetrics;
  onScrollToBottom?: () => void;
  models?: string[];
  selectedModel?: string;
  onSelectModel?: (m: string) => void;
  draftText?: string;
  onDraftConsumed?: () => void;
  onPause?: () => void;
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
  models = ["gemini-3.8-flash-high"],
  selectedModel,
  onSelectModel,
  draftText,
  onDraftConsumed,
  onPause
}) => {
  const [input, setInput] = useState("");
  const [model, setModel] = useState(selectedModel || models[0] || "gemini-3.8-flash-high");
  const [permission, setPermission] = useState("AUTO 模式");
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showPermMenu, setShowPermMenu] = useState(false);
  const [showCommandMenu, setShowCommandMenu] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (selectedModel) {
      setModel(selectedModel);
    }
  }, [selectedModel]);

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
    if (!input.trim() || isLoading) return;
    onSend(input, model, permission);
    setInput("");
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
      {/* 悬浮回底箭头按钮 */}
      {onScrollToBottom && (
        <button
          onClick={onScrollToBottom}
          className="absolute -top-10 right-8 w-8 h-8 rounded-full bg-white border border-gray-200 shadow-md flex items-center justify-center text-gray-500 hover:text-gray-800 transition hover:shadow-lg cursor-pointer"
          title="回到底部"
        >
          <ScrollDown size={16} />
        </button>
      )}

      {/* 底部吸附输入框卡片 */}
      <div className="w-full bg-white dark:bg-[#181920] border border-gray-200 dark:border-gray-800 shadow-sm focus-within:shadow-md focus-within:border-gray-300 dark:focus-within:border-gray-700 rounded-2xl p-3 transition">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="给 super 智能体发消息，输入 / 或点击左下角 + 选择快捷指令..."
          rows={2}
          className="w-full resize-none border-none outline-none text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 text-sm leading-relaxed bg-transparent"
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

            {/* 权限控制下拉项：实际支持的 AUTO 模式与 ASK 模式 */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowPermMenu(!showPermMenu)}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#222534] rounded-lg transition font-medium cursor-pointer"
              >
                <Shield size={13} className="text-blue-600" />
                <span>{permission}</span>
                <ChevronDown size={11} className="text-gray-400" />
              </button>
              
              {showPermMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-20 cursor-default" 
                    onClick={() => setShowPermMenu(false)} 
                  />
                  <div className="absolute left-0 bottom-8 w-52 bg-white dark:bg-[#1a1d27] border border-gray-200 dark:border-[#2a2e3f] shadow-xl rounded-xl py-1 z-30 text-xs text-gray-800 dark:text-gray-200">
                    <div className="px-3 py-1.5 text-[11px] font-semibold text-gray-400 border-b border-gray-100 dark:border-gray-800">
                      运行安全级别
                    </div>
                    {[
                      { id: "AUTO 模式", name: "AUTO 模式 (默认)", desc: "全自动执行，高危命令阻断" },
                      { id: "ASK 模式", name: "ASK 模式 (人工审批)", desc: "敏感修改每次弹窗确认" }
                    ].map((item) => (
                      <div
                        key={item.id}
                        onClick={() => { setPermission(item.id); setShowPermMenu(false); }}
                        className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-[#222534] cursor-pointer flex flex-col transition ${
                          permission === item.id ? "text-blue-600 font-semibold bg-blue-50/50" : "text-gray-700"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span>{item.name}</span>
                          {permission === item.id && <Check size={13} className="text-blue-600" />}
                        </div>
                        <span className="text-[10px] text-gray-400 mt-0.5">{item.desc}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5 relative">
            {/* 模型选择：仅展示真实已配置模型 + 点击空白处关闭 */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowModelMenu(!showModelMenu)}
                className="flex items-center gap-1 text-xs text-gray-700 dark:text-gray-300 font-medium hover:text-blue-600 dark:hover:text-blue-400 px-2 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-[#222534] transition cursor-pointer"
              >
                <span>{model}</span>
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
                      {models.map((m) => {
                        const isCur = m === model;
                        return (
                          <div
                            key={m}
                            onClick={() => handleSelectModel(m)}
                            className={`px-3 py-2 hover:bg-gray-50 dark:hover:bg-[#222534] cursor-pointer flex items-center justify-between transition ${
                              isCur ? "text-blue-600 font-semibold bg-blue-50/60" : "text-gray-700"
                            }`}
                          >
                            <span className="truncate pr-2">{m}</span>
                            {isCur && <Check size={13} className="text-blue-600 shrink-0" />}
                          </div>
                        );
                      })}
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

      {/* 底部遥测状态栏 */}
      <div className="w-full text-center py-1 text-[11px] text-gray-400 dark:text-gray-500 font-mono tracking-tight flex items-center justify-center gap-2">
        <span>{metrics.turns} 轮 · {metrics.steps} 步</span>
        <span>|</span>
        <span>LLM {metrics.total_time} · 工具调用 {metrics.tool_time}</span>
        <span>|</span>
        <span>首 token 平均 2m7s · {metrics.tokens_per_sec} tok/s</span>
        <span>|</span>
        <span>缓存命中 {Math.round(metrics.cache_hit_rate * 100)}%</span>
        <span>|</span>
        <span>输入 {(metrics.prompt_tokens / 1000000).toFixed(1)}M tok · 输出 {(metrics.completion_tokens / 1000).toFixed(1)}k tok</span>
      </div>
    </div>
  );
};
