import React, { useState, useEffect } from "react";
import { 
  ChevronDown, 
  ChevronRight, 
  Check, 
  Copy, 
  Edit2, 
  Code, 
  Sparkles, 
  Atom, 
  Terminal, 
  Loader2, 
  AlertCircle,
  RotateCcw,
  PauseCircle,
  Settings,
  ThumbsUp,
  ThumbsDown,
  ArrowUp,
  ExternalLink,
  Clock
} from "lucide-react";
import { TurnData, TrajectoryStep, UserInputRequest } from "../types";
import { ChatAttachmentItemCard } from "./AttachmentCards";
import { InlineApprovalCard, InlineUserInputCard } from "./InlineInteractionCards";

interface ChatMessageProps {
  turn: TurnData;
  isLoading?: boolean;
  isLatestTurn?: boolean;
  onOpenFile?: (path: string) => void;
  onEditPrompt?: (text: string) => void;
  onResendTurn?: (turnId: number, newPrompt: string) => void;
  onOpenSettings?: () => void;
  approvalReq?: { ticket_id: string; command: string; reason: string } | null;
  onApproveApproval?: (ticketId: string, trustSession: boolean) => void;
  onRejectApproval?: (ticketId: string) => void;
  userInputReq?: UserInputRequest | null;
  onSubmitUserInput?: (requestId: string, selectedOption: string, customInput: string) => void;
  onCancelUserInput?: (requestId: string) => void;
}

// 格式化时间戳为 20:49 形式
function formatTime(ts?: number): string {
  const d = ts ? new Date(ts * 1000) : new Date();
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

// 格式化时间戳为 23:26, 2026/9/26 形式 (对标图三)
function formatFullDateTime(ts?: number): string {
  const d = ts ? new Date(ts * 1000) : new Date();
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  const year = d.getFullYear();
  const month = d.getMonth() + 1;
  const day = d.getDate();
  return `${hours}:${minutes}, ${year}/${month}/${day}`;
}

// 格式化此轮耗时为 "用时 15秒" 或 "用时 15分钟 58秒" (对标图一，按用户发出至回复完成真实时间计算)
function formatTurnElapsed(turn: TurnData, liveElapsed?: number): string {
  const secs = liveElapsed !== undefined 
    ? liveElapsed 
    : (turn.elapsed !== undefined 
        ? turn.elapsed 
        : (turn.timestamp ? Math.max(1, Math.round(Date.now() / 1000 - turn.timestamp)) : 1));

  if (secs >= 60) {
    const mins = Math.floor(secs / 60);
    const remainingSecs = Math.round(secs % 60);
    return `${mins}分钟 ${remainingSecs}秒`;
  }
  return `${Math.max(1, Math.round(secs))}秒`;
}

// 行内 Markdown 标记渲染器 (支持加粗 **bold**、行内代码 `code`、外链 [title](url))
const InlineMarkdown: React.FC<{ text: string }> = ({ text }) => {
  if (!text) return null;

  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g);

  return (
    <>
      {parts.map((part, i) => {
        if (!part) return null;
        if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
          return (
            <code 
              key={i} 
              className="px-1.5 py-0.5 mx-0.5 rounded-md bg-gray-100 dark:bg-[#252837] text-pink-600 dark:text-pink-400 font-mono text-[11.5px] border border-gray-200/70 dark:border-gray-700/70 select-text"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
          return (
            <strong key={i} className="font-semibold text-gray-900 dark:text-white">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("[") && part.includes("](") && part.endsWith(")")) {
          const match = part.match(/\[([^\]]+)\]\(([^)]+)\)/);
          if (match) {
            return (
              <a 
                key={i} 
                href={match[2]} 
                target="_blank" 
                rel="noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5 mx-0.5 font-medium"
              >
                <span>{match[1]}</span>
                <ExternalLink size={10} className="inline opacity-70" />
              </a>
            );
          }
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};

// 检测是否包含 ASCII 字符框线 (┌ ─ ┐ │ └ ┘ ├ ┤ ┬ ┴ ┼ 等)
function hasBoxDrawing(str: string): boolean {
  return /[┌┐└┘│─├┤┬┴┼═║╔╗╚╝╠╣╦╩╬]/.test(str);
}

// ASCII 流程图 / 终端卡片组件 (对标图二)
const AsciiDiagramBlock: React.FC<{ content: string; title?: string }> = ({ content, title }) => {
  return (
    <div className="my-3.5 rounded-xl overflow-hidden border border-gray-300/80 dark:border-gray-700/80 bg-gray-50/90 dark:bg-[#151722] text-gray-800 dark:text-gray-200 shadow-2xs font-mono text-xs">
      <div className="flex items-center justify-between px-3.5 py-2 bg-gray-100/90 dark:bg-[#1e212d] border-b border-gray-200/80 dark:border-gray-700 text-xs text-gray-500 select-none">
        <span className="font-semibold text-gray-700 dark:text-gray-300">
          {title || "架构 / 流程图 / 终端运行卡片"}
        </span>
        <span className="text-[11px] text-gray-400 font-mono">ASCII Diagram</span>
      </div>
      <pre className="p-4 overflow-x-auto text-[12.5px] leading-snug select-text font-mono whitespace-pre text-gray-900 dark:text-gray-100">
        <code>{content}</code>
      </pre>
    </div>
  );
};

// 单个代码块独立组件 (支持右上角复制代码与浅色/深色外观)
const CodeBlock: React.FC<{ code: string; language: string }> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (hasBoxDrawing(code)) {
    return <AsciiDiagramBlock content={code} title={language ? `流程图 (${language})` : undefined} />;
  }

  return (
    <div className="my-3.5 rounded-xl overflow-hidden border border-gray-200/90 dark:border-gray-800 bg-[#f8fafc] dark:bg-[#12141c] text-gray-800 dark:text-gray-200 font-mono text-[13px] shadow-2xs">
      <div className="flex items-center justify-between px-3.5 py-2 bg-[#f1f5f9] dark:bg-[#1a1d27] border-b border-gray-200/80 dark:border-gray-800 select-none text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1.5">
          <Code size={13} className="text-blue-600 dark:text-blue-400" />
          <span className="font-semibold text-gray-700 dark:text-gray-300 lowercase">{language || "text"}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md hover:bg-gray-200/70 dark:hover:bg-[#2d303d] text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition cursor-pointer text-xs font-sans font-medium"
          title="复制代码"
        >
          {copied ? <Check size={13} className="text-green-600 dark:text-green-400" /> : <Copy size={13} />}
          <span>{copied ? "已复制" : "复制代码"}</span>
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-[13px] leading-[1.65] text-[#1e293b] dark:text-[#e2e8f0] bg-[#f8fafc] dark:bg-[#12141c] select-text">
        <code>{code}</code>
      </pre>
    </div>
  );
};

// GFM Markdown 表格解析器与组件 (对标图三)
interface ParsedTable {
  headers: string[];
  alignments: ("left" | "center" | "right")[];
  rows: string[][];
}

const TableBlock: React.FC<{ table: ParsedTable }> = ({ table }) => {
  return (
    <div className="my-3 overflow-x-auto rounded-xl border border-gray-200/90 dark:border-gray-700/80 shadow-2xs bg-white dark:bg-[#1a1c24]">
      <table className="w-full text-xs text-left border-collapse">
        <thead>
          <tr className="bg-gray-100/80 dark:bg-[#222533] border-b border-gray-200/90 dark:border-gray-700/80 text-gray-800 dark:text-gray-200">
            {table.headers.map((h, i) => (
              <th 
                key={i} 
                className={`px-3.5 py-2.5 font-bold whitespace-nowrap ${
                  table.alignments[i] === "center" ? "text-center" : table.alignments[i] === "right" ? "text-right" : "text-left"
                }`}
              >
                <InlineMarkdown text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {table.rows.map((row, rIdx) => (
            <tr key={rIdx} className="hover:bg-gray-50/60 dark:hover:bg-[#1f222e] transition">
              {row.map((cell, cIdx) => (
                <td 
                  key={cIdx} 
                  className={`px-3.5 py-2.5 text-gray-700 dark:text-gray-300 align-top leading-relaxed ${
                    table.alignments[cIdx] === "center" ? "text-center" : table.alignments[cIdx] === "right" ? "text-right" : "text-left"
                  }`}
                >
                  <InlineMarkdown text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

function parseTableRow(line: string): string[] {
  let trimmed = line.trim();
  if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
  if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
  return trimmed.split("|").map((c) => c.trim());
}

// 综合文本行块解析器 (支持标题、列表、分割线、表格、ASCII 框图等)
const TextLinesRenderer: React.FC<{ rawText: string }> = ({ rawText }) => {
  const lines = rawText.split(/\r?\n/);
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // 1. 检测 Markdown 表格 (至少包含表头与分隔线两行)
    if (trimmed.includes("|") && i + 1 < lines.length && /^\s*\|?\s*[-:]+[-| :]*\|\s*$/.test(lines[i + 1])) {
      const headers = parseTableRow(line);
      const sepRow = parseTableRow(lines[i + 1]);
      const alignments: ("left" | "center" | "right")[] = sepRow.map((c) => {
        if (c.startsWith(":") && c.endsWith(":")) return "center";
        if (c.endsWith(":")) return "right";
        return "left";
      });

      const tableRows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().includes("|")) {
        tableRows.push(parseTableRow(lines[i]));
        i++;
      }

      elements.push(
        <TableBlock 
          key={`tbl_${i}`} 
          table={{ headers, alignments, rows: tableRows }} 
        />
      );
      continue;
    }

    // 2. 检测连续的 ASCII 框线段落
    if (hasBoxDrawing(line)) {
      const asciiLines: string[] = [];
      while (i < lines.length && (hasBoxDrawing(lines[i]) || lines[i].trim().startsWith("│") || lines[i].trim().endsWith("│"))) {
        asciiLines.push(lines[i]);
        i++;
      }
      elements.push(
        <AsciiDiagramBlock key={`ascii_${i}`} content={asciiLines.join("\n")} />
      );
      continue;
    }

    // 3. 分割线
    if (/^(\*\*\*|---|___)$/.test(trimmed)) {
      elements.push(
        <hr key={`hr_${i}`} className="my-3.5 border-t border-gray-200 dark:border-gray-700/80" />
      );
      i++;
      continue;
    }

    // 4. 标题 (H1, H2, H3, H4) 对标 Codex 清晰层次
    if (trimmed.startsWith("#")) {
      if (trimmed.startsWith("#### ")) {
        elements.push(
          <h4 key={`h4_${i}`} className="text-sm font-semibold text-gray-800 dark:text-gray-200 mt-3 mb-1">
            <InlineMarkdown text={trimmed.slice(5)} />
          </h4>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("### ")) {
        elements.push(
          <h3 key={`h3_${i}`} className="text-sm font-bold text-gray-900 dark:text-gray-100 mt-3.5 mb-1.5">
            <InlineMarkdown text={trimmed.slice(4)} />
          </h3>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("## ")) {
        elements.push(
          <h2 key={`h2_${i}`} className="text-base font-bold text-gray-900 dark:text-white mt-4 mb-2 pb-1 border-b border-gray-100 dark:border-gray-800">
            <InlineMarkdown text={trimmed.slice(3)} />
          </h2>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("# ")) {
        elements.push(
          <h1 key={`h1_${i}`} className="text-lg font-bold text-gray-900 dark:text-white mt-5 mb-2.5 pb-1.5 border-b border-gray-100 dark:border-gray-800">
            <InlineMarkdown text={trimmed.slice(2)} />
          </h1>
        );
        i++;
        continue;
      }
    }

    // 5. 无序列表 (- 或 *)
    if (/^[-*]\s+/.test(trimmed)) {
      const listContent = trimmed.replace(/^[-*]\s+/, "");
      elements.push(
        <div key={`li_${i}`} className="flex items-start gap-2 my-1.5 ml-1 text-sm leading-[1.75] text-gray-800 dark:text-gray-200">
          <span className="text-gray-400 font-bold shrink-0 text-xs select-none leading-none mt-1.5">•</span>
          <div className="flex-1 min-w-0">
            <InlineMarkdown text={listContent} />
          </div>
        </div>
      );
      i++;
      continue;
    }

    // 6. 有序列表 (如 1. 2.)
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      elements.push(
        <div key={`numli_${i}`} className="flex items-start gap-1.5 my-1.5 ml-1 text-sm leading-[1.75] text-gray-800 dark:text-gray-200">
          <span className="font-semibold text-gray-500 dark:text-gray-400 shrink-0 select-none">
            {numMatch[1]}.
          </span>
          <div className="flex-1 min-w-0">
            <InlineMarkdown text={numMatch[2]} />
          </div>
        </div>
      );
      i++;
      continue;
    }

    // 7. 引用块 (> )
    if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote key={`bq_${i}`} className="my-2.5 pl-3.5 border-l-2 border-blue-500/70 text-gray-600 dark:text-gray-400 text-sm italic bg-blue-50/20 dark:bg-[#1a1d28]/30 py-1.5 rounded-r-lg">
          <InlineMarkdown text={trimmed.slice(2)} />
        </blockquote>
      );
      i++;
      continue;
    }

    // 8. 普通段落 (对标图一：14px 正文字号，1.75 舒适行距)
    elements.push(
      <p key={`p_${i}`} className="leading-[1.75] my-2 text-sm text-gray-800 dark:text-gray-200 select-text">
        <InlineMarkdown text={trimmed} />
      </p>
    );
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
};

// 完整 Markdown 内容渲染器
const MarkdownContent: React.FC<{ content: string }> = ({ content }) => {
  if (!content) return null;
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-1.5 select-text">
      {parts.map((part, idx) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).trim().split("\n");
          let lang = "code";
          let codeContent = lines.join("\n");
          if (lines.length > 0 && /^[a-zA-Z0-9_\-#+.]+$/.test(lines[0].trim())) {
            lang = lines[0].trim();
            codeContent = lines.slice(1).join("\n");
          }
          return <CodeBlock key={idx} code={codeContent} language={lang} />;
        }

        return <TextLinesRenderer key={idx} rawText={part} />;
      })}
    </div>
  );
};

// 汉化工具名称 (对标需求 2：思考过程英文全汉化)
function translateToolName(name: string): string {
  if (!name) return "工具调用";
  const lower = name.toLowerCase().trim();
  if (lower.includes("think") || lower === "assistant" || lower === "thought") return "思考";
  if (lower === "bash" || lower === "exec_command" || lower === "terminal" || lower === "shell" || lower === "cmd") return "终端命令";
  if (lower.includes("write") || lower.includes("edit") || lower.includes("patch") || lower.includes("create")) return "写入文件";
  if (lower.includes("read") || lower.includes("view") || lower.includes("cat")) return "读取文件";
  if (lower.includes("grep") || lower.includes("search") || lower.includes("find")) return "代码检索";
  if (lower.includes("glob") || lower.includes("list_dir") || lower.includes("dir") || lower.includes("ls")) return "检索目录";
  if (lower.includes("skill") || lower.includes("platform")) return "技能平台";
  if (lower.includes("todo") || lower.includes("task")) return "任务规划";
  if (lower.includes("weather")) return "天气查询";
  if (lower.includes("web") || lower.includes("browser") || lower.includes("fetch") || lower.includes("url")) return "网页请求";
  if (lower.includes("user_input") || lower.includes("approval")) return "确认交互";
  if (lower.startsWith("mcp")) return "外部工具";
  return name;
}

// 提取工具执行参数或描述预览
function formatToolDesc(step: TrajectoryStep): string {
  if (step.desc) return step.desc;
  if (step.args) {
    if (typeof step.args === "string") return step.args;
    if (step.args.command) return String(step.args.command);
    if (step.args.path) return String(step.args.path);
    if (step.args.query) return String(step.args.query);
    try {
      return JSON.stringify(step.args);
    } catch {
      return "";
    }
  }
  return "";
}

// 单项思考过程行 (对标图二：去框化无卡片，流光溢彩动态呼吸，全中文展示，点击展开详情)
// 单项思考过程行 (对标图二需求3：彻底删除思考过程右侧时间及多余提示，清爽纯净，点击展开详情)
const ThinkStepRow: React.FC<{ thought: string; isRunning?: boolean }> = ({ 
  thought, 
  isRunning = false 
}) => {
  const [expanded, setExpanded] = useState(false);
  const cleanThought = thought.trim();
  const singleLinePreview = cleanThought.replace(/\r?\n+/g, " ");

  return (
    <div className="py-0.5 text-xs select-none transition-colors">
      <div 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 py-1 px-1.5 -mx-1.5 rounded-lg hover:bg-gray-100/60 dark:hover:bg-[#20232e]/60 transition cursor-pointer group"
      >
        <div className="relative flex items-center justify-center shrink-0">
          <Atom size={13} className={`text-purple-500 dark:text-purple-400 shrink-0 ${isRunning ? "animate-spin-slow" : ""}`} />
        </div>

        <span className="font-medium text-gray-500 dark:text-gray-400 shrink-0">
          思考
        </span>

        <span className="text-gray-300 dark:text-gray-600 select-none">·</span>

        {isRunning ? (
          <span className="shimmer-text font-medium truncate flex-1 min-w-0">
            {singleLinePreview || "正在深入分析与规划中..."}
          </span>
        ) : (
          <span className="text-gray-700 dark:text-gray-300 truncate font-sans text-xs flex-1 min-w-0">
            {singleLinePreview}
          </span>
        )}

        <div className="flex items-center text-gray-400 text-[11px] shrink-0 ml-auto">
          {expanded ? (
            <ChevronDown size={12} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
          ) : (
            <ChevronRight size={12} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="ml-5 pl-3.5 my-1.5 border-l-2 border-purple-200 dark:border-purple-800/80 text-[12.5px] font-sans text-gray-700 dark:text-gray-300 leading-[1.7] whitespace-pre-wrap select-text max-h-64 overflow-y-auto animate-in fade-in duration-150">
          {cleanThought}
        </div>
      )}
    </div>
  );
};

// 单项工具执行行 (对标图二：去框化无卡片，流光溢彩执行动态，全中文展示，点击展开入参出参)
const ToolStepRow: React.FC<{ 
  step: TrajectoryStep; 
  onOpenFile?: (path: string) => void;
  isPaused?: boolean;
  isLoading?: boolean;
}> = ({ step, onOpenFile, isPaused = false, isLoading = false }) => {
  const [expanded, setExpanded] = useState(false);
  const isInterrupted = Boolean(step.status === "running" && (isPaused || !isLoading));
  const isRunning = Boolean(step.status === "running" && !isPaused && isLoading);
  const isError = step.status === "error";

  const chineseType = translateToolName(step.tool || step.display || "");
  const descText = formatToolDesc(step);

  const elapsedText = step.elapsed !== undefined && step.elapsed > 0
    ? `持续了 ${step.elapsed >= 1 ? Math.round(step.elapsed) : step.elapsed.toFixed(1)} 秒` 
    : (isRunning ? "正在执行..." : undefined);

  return (
    <div className="py-0.5 text-xs select-none transition-colors">
      <div 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 py-1 px-1.5 -mx-1.5 rounded-lg hover:bg-gray-100/60 dark:hover:bg-[#20232e]/60 transition cursor-pointer group"
      >
        <div className="relative flex items-center justify-center shrink-0">
          {isRunning ? (
            <Loader2 size={13} className="text-blue-500 animate-spin shrink-0" />
          ) : isInterrupted ? (
            <PauseCircle size={13} className="text-amber-500 shrink-0" />
          ) : isError ? (
            <AlertCircle size={13} className="text-red-500 shrink-0" />
          ) : (
            <Terminal size={13} className="text-amber-500 dark:text-amber-400 shrink-0" />
          )}
        </div>

        <span className="font-medium text-gray-700 dark:text-gray-300 shrink-0">
          {chineseType}
        </span>

        <span className="text-gray-300 dark:text-gray-600 select-none">·</span>

        {isRunning ? (
          <span className="shimmer-text font-medium truncate flex-1 min-w-0">
            {descText || "正在执行..."}
          </span>
        ) : isInterrupted ? (
          <span className="text-amber-600 dark:text-amber-400 truncate font-mono text-[11.5px] flex-1 min-w-0">
            {descText ? `${descText}（已中止）` : "已终止执行"}
          </span>
        ) : step.path ? (
          <span 
            onClick={(e) => {
              e.stopPropagation();
              if (onOpenFile && step.path) onOpenFile(step.path);
            }}
            className="text-gray-600 dark:text-gray-300 hover:text-blue-600 underline truncate font-mono text-[11.5px] flex-1 min-w-0"
          >
            {descText || "查看文件"}
          </span>
        ) : (
          <span className="text-gray-600 dark:text-gray-300 truncate font-mono text-[11.5px] flex-1 min-w-0">
            {descText || "执行完成"}
          </span>
        )}

        <div className="flex items-center text-gray-400 text-[11px] shrink-0 ml-auto">
          {(step.args || step.output) && (
            expanded ? (
              <ChevronDown size={12} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
            ) : (
              <ChevronRight size={12} className="text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
            )
          )}
        </div>
      </div>

      {expanded && (step.args || step.output) && (
        <div className="ml-5 pl-3.5 my-1.5 border-l-2 border-amber-300/80 dark:border-amber-700/80 space-y-2 text-xs animate-in fade-in duration-150">
          {step.args && (
            <div>
              <div className="text-[10px] font-bold text-gray-400 mb-0.5">输入参数</div>
              <pre className="p-2 bg-gray-50 dark:bg-[#161822] border border-gray-200/80 dark:border-gray-800 rounded-lg text-gray-800 dark:text-gray-200 text-xs font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                {typeof step.args === "object" ? JSON.stringify(step.args, null, 2) : step.args}
              </pre>
            </div>
          )}

          {step.output && (
            <div>
              <div className="text-[10px] font-bold text-gray-400 mb-0.5">执行结果</div>
              <pre className="p-2 bg-gray-50 dark:bg-[#161822] border border-gray-200/80 dark:border-gray-800 rounded-lg text-gray-800 dark:text-gray-200 text-xs font-mono whitespace-pre-wrap max-h-52 overflow-y-auto">
                {step.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// 智能诊断 Agent 思考中断根因 (对标需求 3：多维度归因，避免用户误会为仅 API Key 错误)
function diagnoseInterruption(steps: TrajectoryStep[]): {
  title: string;
  desc: string;
  action: "settings" | "resend" | "cmd";
} {
  if (!steps || steps.length === 0) {
    return {
      title: "大模型连接异常或鉴权失败",
      desc: "未能成功建立通信。可能原因：当前模型未配置有效 API 密钥、接口 Base URL 无法连通或模型名称不匹配。",
      action: "settings"
    };
  }

  // 1. 检查是否存在命令执行超时或挂起
  const lastToolStep = [...steps].reverse().find(s => s.type === "tool");
  if (lastToolStep) {
    const out = String(lastToolStep.output || "");
    const argsStr = JSON.stringify(lastToolStep.args || "");
    if (out.includes("执行超时") || out.includes("强杀") || out.includes("TimeoutExpired") || argsStr.includes("start.bat") || argsStr.includes("pause")) {
      return {
        title: "终端命令执行超时或子进程挂起",
        desc: "终端命令执行超时已被系统安全强杀。可能原因：执行的脚本或批处理中包含交互式等待命令（如 pause）、或者启动了未脱离控制台的常驻后台服务。",
        action: "cmd"
      };
    }
    if (out.includes("用户拒绝") || out.includes("安全拦截拒绝")) {
      return {
        title: "命令执行被取消或被安全策略拦截",
        desc: "排查过程中的敏感命令未通过审批或被防火墙规则拦截，Agent 提前收束退出。",
        action: "resend"
      };
    }
  }

  // 2. 检查步数是否过多导致上下文或死循环熔断
  if (steps.length >= 12) {
    return {
      title: "长周期推理中断或步数达到上限",
      desc: `本轮任务已执行 ${steps.length} 个步骤。可能原因：达到模型单轮推理上限、上下文 Token 达到阈值，或触发了多步排查安全熔断。`,
      action: "resend"
    };
  }

  // 3. 通用网络波动或上游服务异常
  return {
    title: "模型思考中断或服务响应超时",
    desc: "在执行多步任务时大模型连接断开或未能输出最终回复。可能原因：服务商网络波动、网关超时（504/502）或响应格式中断。",
    action: "resend"
  };
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ 
  turn, 
  isLoading = false,
  isLatestTurn = false,
  onOpenFile, 
  onEditPrompt,
  onResendTurn,
  onOpenSettings,
  approvalReq,
  onApproveApproval,
  onRejectApproval,
  userInputReq,
  onSubmitUserInput,
  onCancelUserInput
}) => {
  const isPaused = Boolean(turn.is_paused || turn.assistant_response?.includes("【用户已手动暂停】"));
  // 思考状态默认保持展开展示，每一行平铺流光动态，用户可自由折叠与展开 (若已暂停则默认收起)
  const [traceExpanded, setTraceExpanded] = useState<boolean>(() => {
    if (isPaused) return false;
    return true;
  });

  // 动态实时秒数计时器：解决硬编码 6 秒与思考中不计时问题
  const [liveElapsed, setLiveElapsed] = useState<number>(() => {
    if (turn.elapsed) return turn.elapsed;
    if (turn.timestamp) return Math.max(1, Math.round(Date.now() / 1000 - turn.timestamp));
    return 1;
  });

  useEffect(() => {
    if (!isLoading) {
      if (turn.elapsed) setLiveElapsed(turn.elapsed);
      return;
    }
    const updateElapsed = () => {
      if (turn.timestamp) {
        setLiveElapsed(Math.max(1, Math.round(Date.now() / 1000 - turn.timestamp)));
      } else {
        setLiveElapsed((prev) => prev + 1);
      }
    };
    updateElapsed();
    const timer = setInterval(updateElapsed, 1000);
    return () => clearInterval(timer);
  }, [isLoading, turn.timestamp, turn.elapsed]);

  const [copiedAsst, setCopiedAsst] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [liked, setLiked] = useState<boolean | null>(null);

  // 就地原地编辑提问状态 (对标需求 2：点击编辑后直接在气泡处展开编辑并重新发送此轮)
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(turn.user_prompt || "");

  const handleCopyUser = () => {
    navigator.clipboard.writeText(turn.user_prompt);
    setCopiedUser(true);
    setTimeout(() => setCopiedUser(false), 2000);
  };

  const handleCopyAsst = () => {
    navigator.clipboard.writeText(turn.assistant_response || "");
    setCopiedAsst(true);
    setTimeout(() => setCopiedAsst(false), 2000);
  };

  const handleSaveAndResend = () => {
    const trimmed = editText.trim();
    if (!trimmed) return;
    setIsEditing(false);
    if (onResendTurn) {
      onResendTurn(turn.turn_id, trimmed);
    } else if (onEditPrompt) {
      onEditPrompt(trimmed);
    }
  };

  const steps: TrajectoryStep[] = (turn.steps && turn.steps.length > 0) ? turn.steps : [];
  if (steps.length === 0) {
    if (turn.thought) {
      steps.push({
        id: "th_legacy",
        type: "assistant",
        thought: turn.thought
      });
    }
    for (const act of turn.actions || []) {
      steps.push({
        id: act.id,
        type: "tool",
        tool: act.tool,
        display: act.display,
        desc: act.desc,
        path: act.path,
        args: act.args,
        output: act.output,
        status: act.status,
        elapsed: act.elapsed
      });
    }
  }

  const hasSteps = steps.length > 0;
  const timeStr = formatTime(turn.timestamp);
  const fullDateTimeStr = formatFullDateTime(turn.timestamp);
  const elapsedStr = formatTurnElapsed(turn, isLoading ? liveElapsed : turn.elapsed);

  // 当存在待人工审批的敏感操作或用户决策卡片时，强制展开思考追踪区展现卡片；用户在思考中可自由折叠与展开
  const hasPendingInteraction = Boolean(approvalReq || userInputReq);
  const showTrace = hasPendingInteraction ? true : traceExpanded;

  return (
    <div id={`turn-container-${turn.turn_id}`} className="space-y-3.5 mb-6 select-text">
      {/* 1. 用户提问气泡 (支持气泡原地就地编辑重发与复制，支持附件展示) */}
      {(turn.user_prompt || (turn.attachments && turn.attachments.length > 0)) && (
        <div id={`turn-user-${turn.turn_id}`} className="flex items-start gap-2.5 justify-end group scroll-mt-6">
          {!isEditing && (
            <div className="flex items-center gap-1.5 self-end mb-1 text-gray-400 text-xs select-none">
              <span className="text-[11px] font-mono text-gray-400">{timeStr}</span>
              <button
                onClick={handleCopyUser}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-300 transition cursor-pointer"
                title="复制提问"
              >
                {copiedUser ? <Check size={12} className="text-green-600" /> : <Copy size={12} />}
              </button>
              {isLatestTurn && (
                <button
                  onClick={() => {
                    setEditText(turn.user_prompt);
                    setIsEditing(true);
                  }}
                  className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-300 transition cursor-pointer"
                  title="在气泡处编辑并重发"
                >
                  <Edit2 size={12} />
                </button>
              )}
            </div>
          )}

          {isEditing ? (
            /* 原地就地编辑模式 (对标需求 2) */
            <div className="w-full max-w-2xl bg-white dark:bg-[#1a1c24] border border-blue-400 dark:border-blue-500 rounded-2xl p-3 shadow-md space-y-2 select-text">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSaveAndResend();
                  } else if (e.key === "Escape") {
                    setIsEditing(false);
                  }
                }}
                rows={Math.min(8, Math.max(2, editText.split("\n").length))}
                className="w-full resize-none border-none outline-none text-sm text-gray-800 dark:text-gray-100 bg-transparent leading-[1.7]"
                autoFocus
              />
              <div className="flex items-center justify-end gap-2 pt-1 border-t border-gray-100 dark:border-gray-800 text-xs select-none">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-2.5 py-1 rounded-lg text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition cursor-pointer text-xs"
                >
                  取消 (Esc)
                </button>
                <button
                  type="button"
                  onClick={handleSaveAndResend}
                  disabled={!editText.trim()}
                  className="px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition cursor-pointer disabled:opacity-50 flex items-center gap-1 shadow-xs text-xs"
                >
                  <span>保存并重发</span>
                  <ArrowUp size={12} />
                </button>
              </div>
            </div>
          ) : (
            /* 常规展示气泡 */
            <div className="max-w-2xl flex flex-col items-end gap-2 select-text">
              {/* 渲染随本轮提问上传的附件或图片卡片 */}
              {turn.attachments && turn.attachments.length > 0 && (
                <div className="flex flex-wrap gap-2 justify-end max-w-full">
                  {turn.attachments.map((att) => (
                    <ChatAttachmentItemCard key={att.id} attachment={att} />
                  ))}
                </div>
              )}

              {turn.user_prompt && (
                <div className="bg-[#f0f4f9] dark:bg-[#1f222e] text-gray-800 dark:text-gray-100 rounded-xl px-3.5 py-1.5 text-sm leading-normal shadow-2xs border border-gray-200/60 dark:border-gray-800 min-w-[48px] min-h-[30px] inline-flex items-center justify-center">
                  <div className={`whitespace-pre-wrap break-words w-full ${turn.user_prompt.trim().length <= 4 && !turn.user_prompt.includes("\n") ? "text-center font-medium" : "text-left"}`}>
                    {turn.user_prompt}
                  </div>
                </div>
              )}
            </div>
          )}


        </div>
      )}

      {/* 2. 思考过程与工具调用过程 (对标图二：去框化无卡片，流光溢彩动态呼吸，全中文展示，默认展开可自由折叠) */}
      {(hasSteps || isLoading) && (
        <div className="w-full max-w-full mr-auto pl-1 my-1">
          <div className="mb-1.5 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setTraceExpanded(!traceExpanded)}
              className="group/trace inline-flex items-center gap-1.5 text-gray-400 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-xs py-0.5 transition cursor-pointer select-none"
            >
              <Sparkles size={12} className="text-purple-500 shrink-0" />
              <span className="font-normal">
                {traceExpanded 
                  ? `深度思考 · 耗时 ${elapsedStr}` 
                  : `深度思考 · 耗时 ${elapsedStr} (点击展开)`}
              </span>
              {traceExpanded ? (
                <ChevronDown size={13} className="text-gray-400 group-hover/trace:text-gray-600 dark:group-hover/trace:text-gray-300" />
              ) : (
                <ChevronRight size={13} className="text-gray-400 group-hover/trace:text-gray-600 dark:group-hover/trace:text-gray-300" />
              )}
            </button>
          </div>



          {showTrace && (
            <div className="space-y-1.5 py-1 select-text animate-in fade-in duration-150">
              {steps.map((st, i) => {
                if (st.type === "assistant" && st.thought) {
                  return (
                    <ThinkStepRow 
                      key={st.id || `th_${i}`}
                      thought={st.thought}
                      isRunning={isLoading && !isPaused && i === steps.length - 1}
                    />
                  );
                } else if (st.type === "tool") {
                  return (
                    <ToolStepRow 
                      key={st.id || `tool_${i}`} 
                      step={st} 
                      onOpenFile={onOpenFile} 
                      isPaused={isPaused}
                      isLoading={isLoading}
                    />
                  );
                }
                return null;
              })}

              {/* ASK 模式行内安全审批卡片 (置于思考执行流中，对标图二样式，字体加粗区分) */}
              {approvalReq && onApproveApproval && onRejectApproval && (
                <InlineApprovalCard
                  request={approvalReq}
                  onApprove={onApproveApproval}
                  onReject={onRejectApproval}
                />
              )}

              {/* 用户方案决策行内交互卡片 (置于思考执行流中) */}
              {userInputReq && onSubmitUserInput && onCancelUserInput && (
                <InlineUserInputCard
                  request={userInputReq}
                  onSubmit={onSubmitUserInput}
                  onCancel={onCancelUserInput}
                />
              )}

              {isLoading && (
                <div className="flex items-center gap-2 text-xs py-1 select-none font-medium">
                  <Sparkles size={13} className="text-purple-500 animate-spin-slow shrink-0" />
                  <span className="shimmer-text">
                    思考 · 正在深入分析与执行中...
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 若模型调用异常导致思考中断且无最终答复时，在此轮末尾抛出结构化智能诊断卡片 (对标需求 3) */}
      {!isLoading && !turn.assistant_response && (
        <div className="w-full max-w-full mr-auto my-2 animate-in fade-in">
          {(() => {
            const diag = diagnoseInterruption(steps);
            return (
              <div className="p-4 bg-amber-50/90 dark:bg-[#1f1d18] border border-amber-200/90 dark:border-amber-900/50 rounded-2xl text-xs text-amber-900 dark:text-amber-200 flex items-start gap-3 shadow-xs">
                <AlertCircle size={16} className="shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                <div className="flex-1 space-y-1.5">
                  <div className="font-bold text-sm text-amber-900 dark:text-amber-100">{diag.title}</div>
                  <div className="text-xs leading-relaxed text-amber-800/90 dark:text-amber-300/90">
                    {diag.desc}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    {diag.action === "settings" && onOpenSettings ? (
                      <button
                        type="button"
                        onClick={onOpenSettings}
                        className="px-3 py-1.5 bg-amber-200/70 hover:bg-amber-200 dark:bg-amber-900/50 dark:hover:bg-amber-900/80 text-amber-900 dark:text-amber-100 rounded-xl text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-xs"
                      >
                        <Settings size={13} />
                        <span>前往配置模型提供方</span>
                      </button>
                    ) : onResendTurn && turn.user_prompt ? (
                      <button
                        type="button"
                        onClick={() => onResendTurn(turn.turn_id, turn.user_prompt)}
                        className="px-3 py-1.5 bg-amber-200/70 hover:bg-amber-200 dark:bg-amber-900/50 dark:hover:bg-amber-900/80 text-amber-900 dark:text-amber-100 rounded-xl text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-xs"
                      >
                        <RotateCcw size={13} />
                        <span>重新生成此轮</span>
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* 3. 智能体正式输出卡片 (无头像，全宽整齐对齐，对标图四图五优化排版) */}
      {(turn.assistant_response || (!turn.user_prompt && !hasSteps)) && (
        <div className="w-full max-w-full mr-auto group">
          <div className="w-full bg-white dark:bg-[#1a1c24] border border-gray-200/90 dark:border-gray-800 shadow-2xs rounded-2xl px-5 py-4 sm:px-6 sm:py-5 text-sm text-gray-800 dark:text-gray-200 leading-[1.75] select-text">
            {/* 卡片顶部：品牌标识 */}
            <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-gray-100 dark:border-gray-800/80 text-xs text-gray-500 select-none">
              <div className="flex items-center gap-2 font-medium text-gray-700 dark:text-gray-300">
                <span className="font-bold text-gray-900 dark:text-white text-[13.5px]">super</span>
                {!hasSteps && elapsedStr && (
                  <span className="text-[11px] font-mono text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-[#20232e] px-2 py-0.5 rounded-full border border-gray-100 dark:border-gray-800">
                    用时 {elapsedStr}
                  </span>
                )}
              </div>
            </div>

            {/* 核心 Markdown 输出 (表格、流程图、代码块、层级标题，若为异常信息则醒目警示) */}
            {turn.assistant_response ? (
              turn.assistant_response.startsWith("❌") || turn.assistant_response.startsWith("⚠️") ? (
                <div className="p-3 bg-red-50/80 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 rounded-xl text-xs text-red-800 dark:text-red-300 space-y-2">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={16} className="text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                    <div className="flex-1 whitespace-pre-wrap leading-relaxed font-sans">
                      {turn.assistant_response}
                    </div>
                  </div>
                  {onOpenSettings && (
                    <div className="pt-1 flex justify-end">
                      <button
                        type="button"
                        onClick={onOpenSettings}
                        className="px-2.5 py-1 bg-red-100 hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800/60 text-red-700 dark:text-red-200 rounded-lg text-xs font-medium transition cursor-pointer flex items-center gap-1"
                      >
                        <Settings size={12} />
                        <span>前往模型设置</span>
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <MarkdownContent content={turn.assistant_response} />
              )
            ) : isLoading ? (
              <div className="text-xs text-gray-400 italic">正在组织最终答复...</div>
            ) : null}

            {/* 卡片底栏：时间戳 + 复制全文 + 点赞点踩 (对标图三) */}
            {turn.assistant_response && (
              <div className="flex items-center justify-between pt-3.5 mt-4 border-t border-gray-100 dark:border-gray-800/80 text-xs text-gray-400 select-none">
                <div className="flex items-center gap-1.5 font-mono text-gray-400">
                  <Clock size={11} className="opacity-70" />
                  <span>{fullDateTimeStr}</span>
                </div>

                <div className="flex items-center gap-1">
                  {/* 复制全文 */}
                  <button
                    onClick={handleCopyAsst}
                    className="flex items-center gap-1 px-2 py-1 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#252834] transition cursor-pointer"
                    title="复制整段回答"
                  >
                    {copiedAsst ? <Check size={12} className="text-green-600 dark:text-green-400" /> : <Copy size={12} />}
                    <span>{copiedAsst ? "已复制" : "复制"}</span>
                  </button>

                  {/* 点赞 */}
                  <button
                    onClick={() => setLiked(liked === true ? null : true)}
                    className={`p-1 rounded-md transition cursor-pointer ${
                      liked === true 
                        ? "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-[#1e2333]" 
                        : "text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#252834]"
                    }`}
                    title="有帮助"
                  >
                    <ThumbsUp size={12} fill={liked === true ? "currentColor" : "none"} />
                  </button>

                  {/* 点踩 */}
                  <button
                    onClick={() => setLiked(liked === false ? null : false)}
                    className={`p-1 rounded-md transition cursor-pointer ${
                      liked === false 
                        ? "text-red-500 bg-red-50 dark:bg-[#331e23]" 
                        : "text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#252834]"
                    }`}
                    title="需改进"
                  >
                    <ThumbsDown size={12} fill={liked === false ? "currentColor" : "none"} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
