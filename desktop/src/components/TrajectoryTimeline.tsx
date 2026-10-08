import React, { useState } from "react";
import { ChevronDown, ChevronRight, Terminal, FileText, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { TrajectoryStep, ToolAction, TurnData } from "../types";

interface TrajectoryTimelineProps {
  steps?: TrajectoryStep[];
  turns?: TurnData[];
  rawActions?: ToolAction[];
  thoughtText?: string;
  onOpenFile?: (path: string) => void;
}

// 格式化工具入参（LLM 的工具调用请求）
function formatArgs(args?: Record<string, any> | string, desc?: string): string {
  if (!args && !desc) return "";
  if (typeof args === "string") return args;
  if (args && typeof args === "object") {
    if (args.raw) return String(args.raw);
    try {
      return JSON.stringify(args);
    } catch {
      return desc || "";
    }
  }
  return desc || "";
}

// 格式化工具执行输出预览（工具执行结果）
function formatOutputPreview(output?: string, status?: string): string {
  if (status === "running") return "正在执行...";
  if (!output) return "执行完成";
  const clean = output.replace(/\r?\n/g, " ").trim();
  return clean.length > 130 ? clean.slice(0, 127) + "..." : clean;
}

// 规范化多来源步骤数据
export function normalizeTrajectorySteps(
  steps?: TrajectoryStep[],
  turns?: TurnData[],
  rawActions?: ToolAction[],
  thoughtText?: string
): TrajectoryStep[] {
  if (steps && steps.length > 0) return steps;

  const collected: TrajectoryStep[] = [];
  if (turns && turns.length > 0) {
    for (const turn of turns) {
      if (turn.steps && turn.steps.length > 0) {
        collected.push(...turn.steps);
      } else {
        if (turn.thought) {
          collected.push({
            id: `th_${turn.turn_id}`,
            type: "assistant",
            thought: turn.thought,
            timestamp: turn.timestamp || Date.now()
          });
        }
        for (const act of turn.actions || []) {
          collected.push({
            id: act.id,
            type: "tool",
            tool: act.tool,
            display: act.display,
            desc: act.desc,
            path: act.path,
            args: act.args,
            output: act.output,
            status: act.status,
            elapsed: act.elapsed,
            timestamp: act.timestamp
          });
        }
      }
    }
  }

  if (collected.length === 0 && rawActions && rawActions.length > 0) {
    for (const act of rawActions) {
      collected.push({
        id: act.id,
        type: "tool",
        tool: act.tool,
        display: act.display,
        desc: act.desc,
        path: act.path,
        args: act.args,
        output: act.output,
        status: act.status,
        elapsed: act.elapsed,
        timestamp: act.timestamp
      });
    }
    if (thoughtText) {
      collected.push({
        id: "th_raw",
        type: "assistant",
        thought: thoughtText,
        timestamp: Date.now()
      });
    }
  }

  return collected;
}

export const TrajectoryTimeline: React.FC<TrajectoryTimelineProps> = ({
  steps,
  turns,
  rawActions,
  thoughtText,
  onOpenFile
}) => {
  const [expandedMap, setExpandedMap] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const allSteps = normalizeTrajectorySteps(steps, turns, rawActions, thoughtText);

  if (allSteps.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-400 select-none">
        当前会话暂无执行轨迹与工具调用记录
      </div>
    );
  }

  return (
    <div className="max-w-4xl w-full mx-auto py-2">
      {/* 轨迹时间线流（100% 对标图一标准：连贯时间线、醒目 TOOL / ASSISTANT 徽标、入参与出参分明） */}
      <div className="relative pl-7 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-px before:bg-gray-200 dark:before:bg-gray-800 space-y-4">
        {allSteps.map((step, idx) => {
          const stepId = step.id || `step_${idx}`;
          const isExpanded = Boolean(expandedMap[stepId]);
          const isTool = step.type === "tool";

          return (
            <div key={stepId} className="relative group text-xs select-text">
              {/* 时间线节点小圆点 */}
              <div className="w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-600 group-hover:bg-blue-500 absolute left-[-18px] top-2 -translate-x-1/2 ring-4 ring-white dark:ring-[#0f1117] transition" />

              {isTool ? (
                /* 1. TOOL 节点 (图一标准：橙黄 TOOL 徽标 + 工具名与请求参数 + 箭头 + 执行结果输出) */
                <div className="bg-white dark:bg-[#1a1c24] border border-gray-200/80 dark:border-gray-800 rounded-xl p-2.5 shadow-2xs hover:border-gray-300 dark:hover:border-gray-700 transition">
                  <div 
                    onClick={() => toggleExpand(stepId)}
                    className="flex items-start gap-2.5 cursor-pointer"
                  >
                    {/* TOOL 醒目标签 */}
                    <span className="px-2 py-0.5 text-[10px] font-bold font-mono tracking-wider text-[#b45309] bg-[#fef3c7] dark:bg-[#38260b] dark:text-[#fcd34d] border border-[#fde68a] dark:border-[#78350f] rounded shrink-0 select-none mt-0.5">
                      TOOL
                    </span>

                    {/* 工具名称、请求入参、箭头与执行结果摘要 */}
                    <div className="flex-1 min-w-0 flex items-baseline gap-2 flex-wrap font-mono text-[11px]">
                      <span className="font-bold text-gray-900 dark:text-gray-100">
                        {step.tool || step.display || "tool"}
                      </span>

                      {/* LLM 的工具调用请求参数 */}
                      <span 
                        className="text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-[#222530] border border-gray-200/70 dark:border-gray-700/80 px-1.5 py-0.5 rounded truncate max-w-md font-mono"
                        title={formatArgs(step.args, step.desc)}
                      >
                        {formatArgs(step.args, step.desc) || "{}"}
                      </span>

                      {/* 转换箭头 */}
                      <span className="text-gray-400 font-bold select-none">→</span>

                      {/* 工具执行结果输出 */}
                      <span 
                        className={`truncate max-w-lg font-mono ${step.status === "error" ? "text-red-500 font-semibold" : "text-gray-500 dark:text-gray-400"}`}
                        title={step.output}
                      >
                        {formatOutputPreview(step.output, step.status)}
                      </span>
                    </div>

                    {/* 耗时与展开切换 */}
                    <div className="flex items-center gap-1.5 text-gray-400 text-[10px] shrink-0 font-mono ml-auto select-none">
                      {step.elapsed !== undefined && <span>{step.elapsed}s</span>}
                      {step.status === "running" && <Loader2 size={12} className="animate-spin text-amber-500" />}
                      {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </div>
                  </div>

                  {/* 展开的完整详情：展示 IN (请求参数) 与 OUT (执行结果) */}
                  {isExpanded && (
                    <div className="mt-2.5 pt-2.5 border-t border-gray-100 dark:border-gray-800 font-mono text-[11px] space-y-2.5 animate-in fade-in duration-100">
                      {step.args && (
                        <div>
                          <div className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                            <span>IN</span>
                            <span className="text-gray-400 font-normal">LLM 的工具调用请求</span>
                          </div>
                          <pre className="p-2.5 bg-gray-50 dark:bg-[#1e202a] border border-gray-200/80 dark:border-gray-700/80 rounded-lg text-gray-800 dark:text-gray-200 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed select-text">
                            {typeof step.args === "object" ? JSON.stringify(step.args, null, 2) : step.args}
                          </pre>
                        </div>
                      )}

                      {step.output && (
                        <div>
                          <div className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                            <span>OUT</span>
                            <span className="text-gray-400 font-normal">工具执行结果输出</span>
                          </div>
                          <pre className="p-2.5 bg-gray-50 dark:bg-[#1e202a] border border-gray-200/80 dark:border-gray-700/80 rounded-lg text-gray-800 dark:text-gray-200 whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed select-text">
                            {step.output}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                /* 2. ASSISTANT 节点 (图一标准：淡紫 ASSISTANT 徽标 + LLM 的思考过程与计划) */
                <div className="bg-white dark:bg-[#1a1c24] border border-gray-200/80 dark:border-gray-800 rounded-xl p-2.5 shadow-2xs hover:border-gray-300 dark:hover:border-gray-700 transition">
                  <div className="flex items-start gap-2.5">
                    {/* ASSISTANT 醒目标签 */}
                    <span className="px-2 py-0.5 text-[10px] font-bold font-mono tracking-wider text-[#7c3aed] dark:text-[#c084fc] bg-[#f5f3ff] dark:bg-[#2e1d4d] border border-[#ddd6fe] dark:border-[#582b8c] rounded shrink-0 select-none mt-0.5">
                      ASSISTANT
                    </span>

                    {/* LLM 的思考过程（计划下一步做什么） */}
                    <div className="flex-1 text-xs text-gray-800 dark:text-gray-200 leading-relaxed font-sans select-text whitespace-pre-wrap break-words">
                      {step.thought || step.content}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
