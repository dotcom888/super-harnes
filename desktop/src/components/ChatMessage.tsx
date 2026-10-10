import React, { useState, useEffect } from "react";
import { 
  User, 
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
  Settings,
  ThumbsUp,
  ThumbsDown,
  ArrowUp,
  ExternalLink,
  Clock
} from "lucide-react";
import { TurnData, TrajectoryStep, UserInputRequest } from "../types";
import { LOGO_DATA_URI } from "../assets/logoData";
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

// 格式化此轮耗时为 "用时 15秒" 或 "用时 15分钟 58秒" (对标图一)
function formatTurnElapsed(turn: TurnData): string {
  if (turn.elapsed) {
    if (turn.elapsed >= 60) {
      const mins = Math.floor(turn.elapsed / 60);
      const secs = Math.round(turn.elapsed % 60);
      return `${mins}分钟 ${secs}秒`;
    }
    return `${Math.round(turn.elapsed)}秒`;
  }

  let totalSecs = 0;
  if (turn.steps && turn.steps.length > 0) {
    for (const st of turn.steps) {
      if (st.elapsed) totalSecs += st.elapsed;
    }
  }
  if (totalSecs === 0 && turn.actions && turn.actions.length > 0) {
    for (const act of turn.actions) {
      if (act.elapsed) totalSecs += act.elapsed;
    }
  }

  if (totalSecs > 0) {
    if (totalSecs >= 60) {
      const mins = Math.floor(totalSecs / 60);
      const secs = Math.round(totalSecs % 60);
      return `${mins}分钟 ${secs}秒`;
    }
    return `${Math.round(totalSecs)}秒`;
  }

  const stepCount = (turn.steps?.length || turn.actions?.length || 0);
  if (stepCount > 0) {
    return `${Math.max(2, stepCount * 3)}秒`;
  }
  return "6秒";
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
    <div className="my-3 rounded-xl overflow-hidden border border-gray-300/80 dark:border-gray-700 bg-gray-50/90 dark:bg-[#181a24] text-gray-800 dark:text-gray-200 shadow-2xs font-mono text-xs">
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-100/90 dark:bg-[#20232e] border-b border-gray-200/80 dark:border-gray-700 text-[11px] text-gray-500 select-none">
        <span className="font-semibold text-gray-700 dark:text-gray-300">
          {title || "架构 / 流程图 / 终端运行卡片"}
        </span>
        <span className="text-[10px] text-gray-400">ASCII Diagram</span>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[12px] leading-relaxed select-text font-mono whitespace-pre text-gray-900 dark:text-gray-100">
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
    <div className="my-3 rounded-xl overflow-hidden border border-gray-200/80 dark:border-gray-700/80 bg-[#f8fafc] dark:bg-[#181920] text-gray-800 dark:text-gray-200 font-mono text-xs shadow-2xs">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#f1f5f9] dark:bg-[#20222b] border-b border-gray-200/80 dark:border-gray-700/80 select-none text-[11px] text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1.5">
          <Code size={12} className="text-blue-600 dark:text-blue-400" />
          <span className="font-semibold text-gray-700 dark:text-gray-300 lowercase">{language || "text"}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-gray-200/70 dark:hover:bg-[#2d303d] text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition cursor-pointer"
          title="复制代码"
        >
          {copied ? <Check size={12} className="text-green-600 dark:text-green-400" /> : <Copy size={12} />}
          <span>{copied ? "已复制" : "复制代码"}</span>
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[12px] leading-relaxed text-[#1e293b] dark:text-[#e2e8f0] bg-[#f8fafc] dark:bg-[#181920] select-text">
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

    // 4. 标题 (H1, H2, H3, H4)
    if (trimmed.startsWith("#")) {
      if (trimmed.startsWith("#### ")) {
        elements.push(
          <h4 key={`h4_${i}`} className="text-xs font-semibold text-gray-800 dark:text-gray-200 mt-2.5 mb-1">
            <InlineMarkdown text={trimmed.slice(5)} />
          </h4>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("### ")) {
        elements.push(
          <h3 key={`h3_${i}`} className="text-xs font-bold text-gray-900 dark:text-gray-100 mt-3 mb-1">
            <InlineMarkdown text={trimmed.slice(4)} />
          </h3>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("## ")) {
        elements.push(
          <h2 key={`h2_${i}`} className="text-sm font-bold text-gray-900 dark:text-white mt-3.5 mb-1.5 pb-0.5 border-b border-gray-100 dark:border-gray-800">
            <InlineMarkdown text={trimmed.slice(3)} />
          </h2>
        );
        i++;
        continue;
      }
      if (trimmed.startsWith("# ")) {
        elements.push(
          <h1 key={`h1_${i}`} className="text-base font-bold text-gray-900 dark:text-white mt-4 mb-2 pb-1 border-b border-gray-100 dark:border-gray-800">
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
        <div key={`li_${i}`} className="flex items-start gap-2 my-1 ml-1 text-xs leading-relaxed text-gray-800 dark:text-gray-200">
          <span className="text-blue-500 font-bold shrink-0 text-sm select-none leading-none mt-0.5">•</span>
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
        <div key={`numli_${i}`} className="flex items-start gap-1.5 my-1 ml-1 text-xs leading-relaxed text-gray-800 dark:text-gray-200">
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
        <blockquote key={`bq_${i}`} className="my-2 pl-3 border-l-2 border-blue-500/70 text-gray-600 dark:text-gray-400 text-xs italic bg-blue-50/20 dark:bg-[#1a1d28]/30 py-1 rounded-r-lg">
          <InlineMarkdown text={trimmed.slice(2)} />
        </blockquote>
      );
      i++;
      continue;
    }

    // 8. 普通段落
    elements.push(
      <p key={`p_${i}`} className="leading-relaxed my-1 text-xs text-gray-800 dark:text-gray-200 select-text">
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

// 单项思考过程卡片 (对标图一：不换行，单行自动截断折叠，带动态图标与等距排版)
const ThinkStepCard: React.FC<{ thought: string }> = ({ thought }) => {
  const [expanded, setExpanded] = useState(false);
  const cleanThought = thought.trim();
  const singleLinePreview = cleanThought.replace(/\r?\n+/g, " ");

  return (
    <div className="border border-gray-200/80 dark:border-gray-700/80 rounded-xl bg-white dark:bg-[#1a1c24] overflow-hidden shadow-2xs text-xs font-mono my-1 transition-all">
      <div 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-3 py-2 bg-purple-50/30 dark:bg-[#201d2e]/40 hover:bg-purple-50/60 dark:hover:bg-[#262238] transition cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 truncate flex-1 min-w-0 pr-2">
          <div className="relative flex items-center justify-center shrink-0">
            <Atom size={13} className="text-purple-600 dark:text-purple-400 animate-spin-slow animate-pulse-glow shrink-0" />
          </div>

          <span className="font-semibold text-purple-700 dark:text-purple-300 shrink-0">
            Think ·
          </span>

          <span className="text-gray-700 dark:text-gray-300 truncate font-sans text-xs">
            {singleLinePreview}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-gray-400 text-[11px] shrink-0">
          <span className="text-[10px] text-gray-400 font-sans hidden sm:inline">
            {expanded ? "收起" : "展开"}
          </span>
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </div>
      </div>

      {expanded && (
        <div className="p-3 border-t border-purple-100/80 dark:border-gray-800 bg-purple-50/20 dark:bg-[#181622] text-xs font-sans text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap select-text max-h-60 overflow-y-auto">
          {cleanThought}
        </div>
      )}
    </div>
  );
};

// 单项工具调用卡片 (对标图一：单行紧凑折叠，带动态终端脉冲动画，IN/OUT 规范折叠)
const ToolStepCard: React.FC<{ step: TrajectoryStep; onOpenFile?: (path: string) => void }> = ({ step, onOpenFile }) => {
  const [expanded, setExpanded] = useState(false);
  const isRunning = step.status === "running";
  const isError = step.status === "error";

  const toolTitle = step.display || step.tool || "Tool";
  const descText = step.desc || (typeof step.args === "object" ? JSON.stringify(step.args) : String(step.args || ""));

  return (
    <div className="border border-gray-200/80 dark:border-gray-700/80 rounded-xl bg-white dark:bg-[#1a1c24] overflow-hidden shadow-2xs text-xs font-mono my-1 transition-all">
      <div 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-3 py-2 bg-gray-50/70 dark:bg-[#20232e] hover:bg-gray-100/70 dark:hover:bg-[#272b38] transition cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 truncate flex-1 min-w-0 pr-2">
          {isRunning ? (
            <Loader2 size={13} className="text-amber-500 animate-spin shrink-0" />
          ) : isError ? (
            <AlertCircle size={13} className="text-red-500 shrink-0" />
          ) : (
            <div className="relative flex items-center justify-center shrink-0">
              <Terminal size={13} className="text-amber-500 dark:text-amber-400 animate-tool-pulse shrink-0" />
            </div>
          )}

          <span className="font-semibold text-gray-800 dark:text-gray-200 shrink-0">
            Tool call · {toolTitle}
          </span>
          <span className="text-gray-400">·</span>

          {step.path ? (
            <span 
              onClick={(e) => {
                e.stopPropagation();
                if (onOpenFile && step.path) onOpenFile(step.path);
              }}
              className="text-gray-600 dark:text-gray-300 hover:text-blue-600 underline truncate"
            >
              {descText}
            </span>
          ) : (
            <span className="text-gray-500 dark:text-gray-400 truncate">{descText}</span>
          )}
        </div>

        <div className="flex items-center gap-1.5 text-gray-400 text-[11px] shrink-0">
          {step.elapsed !== undefined && <span>{step.elapsed}s</span>}
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </div>
      </div>

      {expanded && (
        <div className="p-3 border-t border-gray-100 dark:border-gray-800 space-y-2 bg-gray-50/40 dark:bg-[#161820] text-[11px]">
          {step.args && (
            <div>
              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">IN 参数</div>
              <pre className="p-2.5 bg-white dark:bg-[#1e202a] border border-gray-200/80 dark:border-gray-700 rounded-lg text-gray-800 dark:text-gray-200 whitespace-pre-wrap max-h-40 overflow-y-auto">
                {typeof step.args === "object" ? JSON.stringify(step.args, null, 2) : step.args}
              </pre>
            </div>
          )}

          {step.output && (
            <div>
              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">OUT 输出</div>
              <pre className="p-2.5 bg-white dark:bg-[#1e202a] border border-gray-200/80 dark:border-gray-700 rounded-lg text-gray-800 dark:text-gray-200 whitespace-pre-wrap max-h-52 overflow-y-auto">
                {step.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

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
  const [traceExpanded, setTraceExpanded] = useState(false);

  // 运行中默认展开查看实时轨迹；一旦运行结束或暂停，思考过程自动收起折叠 (对标需求 4)
  useEffect(() => {
    if (!isLoading) {
      setTraceExpanded(false);
    }
  }, [isLoading]);
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
  const elapsedStr = formatTurnElapsed(turn);

  // 当存在待人工审批的敏感操作或用户决策卡片时，强制展开思考追踪区展现卡片 (对标需求 1)
  const hasPendingInteraction = Boolean(approvalReq || userInputReq);
  const showTrace = isLoading || hasPendingInteraction ? true : traceExpanded;

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
                className="w-full resize-none border-none outline-none text-xs text-gray-800 dark:text-gray-100 bg-transparent leading-relaxed"
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
                <div className="bg-[#f0f4f9] dark:bg-[#1f222e] text-gray-800 dark:text-gray-100 rounded-2xl px-4 py-2.5 text-xs leading-relaxed shadow-2xs border border-gray-100/90 dark:border-gray-800">
                  <div className="whitespace-pre-wrap break-words">{turn.user_prompt}</div>
                </div>
              )}
            </div>
          )}

          <div className="w-7 h-7 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 flex items-center justify-center text-xs font-semibold shrink-0 shadow-2xs mt-0.5 select-none">
            <User size={15} />
          </div>
        </div>
      )}

      {/* 2. 思考过程与工具调用过程 (对标图四：执行时流式展开，完成后自动折叠，发消息立即显示动效) */}
      {(hasSteps || isLoading) && (
        <div className="max-w-3xl mr-auto pl-10">
          {!isLoading && (turn.assistant_response || hasSteps) && hasSteps && (
            <div className="mb-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTraceExpanded(!traceExpanded)}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-50/90 dark:bg-[#181a22] hover:bg-gray-100 dark:hover:bg-[#20232d] border border-gray-200/80 dark:border-gray-700/80 rounded-xl text-xs text-gray-600 dark:text-gray-300 font-medium transition cursor-pointer shadow-2xs"
              >
                <Sparkles size={13} className="text-purple-600 dark:text-purple-400 shrink-0" />
                <span>
                  {traceExpanded ? "收起思考与执行过程" : `已深度思考与执行 (${steps.length} 项步骤 · 展开查看)`}
                </span>
                {traceExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </button>
            </div>
          )}

          {/* 若模型调用异常导致思考中断且无答复时，在此处抛出报错信息 (对标需求 4) */}
          {!isLoading && !turn.assistant_response && hasSteps && (
            <div className="my-2 p-3 bg-red-50/80 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 rounded-xl text-xs text-red-700 dark:text-red-300 flex items-start gap-2.5 animate-in fade-in">
              <AlertCircle size={15} className="shrink-0 mt-0.5 text-red-600 dark:text-red-400" />
              <div className="flex-1 space-y-1.5">
                <div className="font-semibold">模型思考中断，未能生成最终回复</div>
                <div className="text-[11px] leading-relaxed text-red-600/90 dark:text-red-400/90">
                  可能原因：当前选择的模型未配置有效 API 密钥、接口地址无法连通或模型名称不匹配。
                </div>
                {onOpenSettings && (
                  <button
                    type="button"
                    onClick={onOpenSettings}
                    className="mt-1 px-2.5 py-1 bg-red-100 hover:bg-red-200 dark:bg-red-900/40 dark:hover:bg-red-900/60 text-red-700 dark:text-red-200 rounded-lg text-xs font-medium transition cursor-pointer flex items-center gap-1.5"
                  >
                    <Settings size={12} />
                    <span>前往配置模型提供方</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {showTrace && (
            <div className="space-y-1.5 py-1 select-text animate-in fade-in duration-150">
              {steps.map((st, i) => {
                if (st.type === "assistant" && st.thought) {
                  return (
                    <ThinkStepCard 
                      key={st.id || `th_${i}`}
                      thought={st.thought}
                    />
                  );
                } else if (st.type === "tool") {
                  return (
                    <ToolStepCard 
                      key={st.id || `tool_${i}`} 
                      step={st} 
                      onOpenFile={onOpenFile} 
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
                <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 py-1.5 animate-pulse font-medium">
                  <Loader2 size={13} className="animate-spin" />
                  <span>super 正在深度思考与执行下一步排查...</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 3. 智能体正式输出卡片 (对标图一、图二、图三) */}
      {(turn.assistant_response || (!turn.user_prompt && !hasSteps)) && (
        <div className="flex items-start gap-3 max-w-3xl mr-auto group">
          <img 
            src={LOGO_DATA_URI} 
            alt="super avatar" 
            className="w-7 h-7 object-contain rounded-xl shrink-0 mt-1 shadow-2xs select-none" 
          />
          <div className="flex-1 bg-white dark:bg-[#1a1c24] border border-gray-200 dark:border-gray-800 shadow-2xs rounded-2xl px-4 py-3.5 text-xs text-gray-800 dark:text-gray-200 leading-relaxed select-text">
            {/* 卡片顶部：品牌标识 + 耗时徽标 (对标图一) */}
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100 dark:border-gray-800 text-xs text-gray-500 select-none">
              <div className="flex items-center gap-2 font-medium text-gray-700 dark:text-gray-300">
                <span className="font-bold text-gray-900 dark:text-white">super</span>
                {/* 耗时徽标 (对标图一: 用时 15秒 / 15分钟 58秒) */}
                <span className="text-[11px] font-mono text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-[#20232e] px-2 py-0.5 rounded-full border border-gray-100 dark:border-gray-800">
                  用时 {elapsedStr}
                </span>
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
              <div className="flex items-center justify-between pt-3 mt-3 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-gray-400 select-none">
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
