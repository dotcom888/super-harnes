export type ExecutionModeId = "auto" | "edit_auto" | "plan" | "manual";

export interface ExecutionModeOption {
  id: ExecutionModeId;
  name: string;
  badge: string;
  desc: string;
  iconName: "Zap" | "FileEdit" | "Compass" | "ShieldCheck";
}

export const EXECUTION_MODES: ExecutionModeOption[] = [
  {
    id: "auto",
    name: "Auto 模式",
    badge: "Auto",
    desc: "日常开发最推荐，效率与安全兼顾（安全改不问，危险跑才问）",
    iconName: "Zap"
  },
  {
    id: "edit_auto",
    name: "Edit automatically",
    badge: "Edit",
    desc: "适合明确目标、快速改代码（直接改不问，命令才问）",
    iconName: "FileEdit"
  },
  {
    id: "plan",
    name: "Plan 模式",
    badge: "Plan",
    desc: "适合大重构、复杂任务，先审批（不动手，先出方案）",
    iconName: "Compass"
  },
  {
    id: "manual",
    name: "Manual 模式",
    badge: "Manual",
    desc: "步步为营，最安全但最累（编辑文件与执行命令每次都问）",
    iconName: "ShieldCheck"
  }
];

export function normalizeModeId(mode?: string): ExecutionModeId {
  if (!mode) return "auto";
  const m = mode.trim().toLowerCase();
  if (m.includes("plan")) return "plan";
  if (m.includes("edit")) return "edit_auto";
  if (m.includes("manual") || m.includes("ask") || m.includes("always_ask")) return "manual";
  return "auto";
}

export function getModeDisplayName(mode?: string): string {
  const norm = normalizeModeId(mode);
  switch (norm) {
    case "edit_auto":
      return "Edit automatically";
    case "plan":
      return "Plan 模式";
    case "manual":
      return "Manual 模式";
    default:
      return "Auto 模式";
  }
}
