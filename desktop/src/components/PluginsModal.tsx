import React, { useEffect, useState } from "react";
import { X, Puzzle, CheckCircle, Terminal, Folder, Globe, Cpu, Wrench } from "lucide-react";

interface PluginsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PluginsModal: React.FC<PluginsModalProps> = ({ isOpen, onClose }) => {
  const [skills, setSkills] = useState<any[]>([]);
  const [mcp, setMcp] = useState<any>({ clients: [], tools: [], servers_detail: [] });
  const [activeTab, setActiveTab] = useState<"skills" | "mcp">("skills");

  useEffect(() => {
    if (!isOpen) return;
    fetch("http://127.0.0.1:8765/api/skills")
      .then((res) => res.json())
      .then((data) => setSkills(data.skills || []))
      .catch(() => {});

    fetch("http://127.0.0.1:8765/api/mcp")
      .then((res) => res.json())
      .then((data) => setMcp(data || { clients: [], tools: [], servers_detail: [] }))
      .catch(() => {});
  }, [isOpen]);

  if (!isOpen) return null;

  const workspaceSkills = skills.filter((s) => s.source_scope === "workspace");
  const userSkills = skills.filter((s) => s.source_scope !== "workspace");

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 select-none">
      <div 
        className="w-[660px] h-[560px] bg-white dark:bg-[#12141c] rounded-2xl shadow-2xl border border-gray-200 dark:border-[#222634] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150 transition-colors"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-50 dark:bg-[#231b31] flex items-center justify-center text-purple-600 dark:text-purple-400">
              <Puzzle size={16} />
            </div>
            <div>
              <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">插件与技能中心 (Skills & MCP)</span>
              <p className="text-[11px] text-gray-400">管理智能体的专家 SOP 规范与外部 MCP 系统集成能力</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#20232e] rounded-lg transition cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* 标签栏 */}
        <div className="flex items-center border-b border-gray-100 dark:border-gray-800 px-5 gap-6 text-xs font-medium bg-gray-50/50 dark:bg-[#161822]">
          <button
            onClick={() => setActiveTab("skills")}
            className={`py-3 border-b-2 transition flex items-center gap-1.5 cursor-pointer ${
              activeTab === "skills" 
                ? "border-purple-600 text-purple-600 dark:text-purple-400 font-semibold" 
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            <span>挂载技能 SOP ({skills.length})</span>
            <span className="text-[10px] text-gray-400 font-normal">
              (工作区 {workspaceSkills.length} + 全局 {userSkills.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab("mcp")}
            className={`py-3 border-b-2 transition flex items-center gap-1.5 cursor-pointer ${
              activeTab === "mcp" 
                ? "border-purple-600 text-purple-600 dark:text-purple-400 font-semibold" 
                : "border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            <span>外部 MCP 服务 ({mcp.clients?.length || 2})</span>
          </button>
        </div>

        {/* 列表内容 */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2.5 text-xs">
          {activeTab === "skills" ? (
            <>
              <div className="bg-purple-50/50 dark:bg-[#1a1728] border border-purple-100 dark:border-[#2f2747] p-2.5 rounded-xl text-[11px] text-purple-700 dark:text-purple-300 leading-relaxed">
                💡 <strong>技能的作用：</strong> Skills 是提供给大模型的专业工作流 SOP 指南（通过 SKILL.md 文档注入）。智能体会根据当前任务自动激活匹配的技能规范。
              </div>

              {skills.map((s, idx) => {
                const isWorkspace = s.source_scope === "workspace";
                return (
                  <div 
                    key={idx} 
                    className="p-3 border border-gray-200/80 dark:border-gray-800 rounded-xl bg-gray-50/60 dark:bg-[#181a24] hover:border-gray-300 dark:hover:border-gray-700 transition"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono text-xs">
                            {s.name}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium inline-flex items-center gap-1 ${
                            isWorkspace 
                              ? "bg-blue-50 dark:bg-[#192233] text-blue-600 dark:text-blue-400 border border-blue-200/60 dark:border-blue-900/50" 
                              : "bg-purple-50 dark:bg-[#231b31] text-purple-600 dark:text-purple-400 border border-purple-200/60 dark:border-purple-900/50"
                          }`}>
                            {isWorkspace ? <Folder size={10} /> : <Globe size={10} />}
                            <span>{isWorkspace ? "工作区 .skills" : "用户全局 ~/.agents/skills"}</span>
                          </span>
                        </div>
                        <p className="text-gray-600 dark:text-gray-400 mt-1 leading-relaxed text-[11.5px]">
                          {s.description || "（暂无详细说明）"}
                        </p>
                        {s.directory && (
                          <div className="text-[10px] text-gray-400 dark:text-gray-500 font-mono mt-1 truncate">
                            路径: {s.directory}
                          </div>
                        )}
                      </div>
                      <CheckCircle size={15} className="text-green-500 shrink-0 mt-0.5" />
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="space-y-3">
              <div className="bg-blue-50/50 dark:bg-[#151f30] border border-blue-100 dark:border-[#223350] p-2.5 rounded-xl text-[11px] text-blue-700 dark:text-blue-300 leading-relaxed">
                🔌 <strong>MCP 的作用：</strong> MCP (Model Context Protocol) 是模型上下文协议，用于将智能体安全连通到本地或外部子进程服务（如计算引擎、系统探针、数据库）。通过 MCP，智能体可动态获取扩展工具。
              </div>

              {/* 展示具体 MCP 服务详情 */}
              {[
                {
                  id: "calculator",
                  name: "calculator (内置计算服务)",
                  script: "mcp/servers/calc_server.py",
                  desc: "提供高精度数学运算与科学计算支持，免除大模型心算幻觉。",
                  tools: ["mcp__calculator__calculate"]
                },
                {
                  id: "system_info",
                  name: "system_info (系统信息探针)",
                  script: "mcp/servers/sysinfo_server.py",
                  desc: "实时采集宿主机 CPU、内存、磁盘与操作系统运行环境指标。",
                  tools: ["mcp__system_info__get_system_info"]
                }
              ].map((srv, idx) => (
                <div key={idx} className="p-3.5 border border-gray-200/80 dark:border-gray-800 rounded-xl bg-gray-50/60 dark:bg-[#181a24]">
                  <div className="flex items-center justify-between pb-1.5 border-b border-gray-100 dark:border-gray-800/80">
                    <div className="flex items-center gap-2">
                      <Terminal size={14} className="text-blue-600 dark:text-blue-400" />
                      <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono text-xs">{srv.name}</span>
                    </div>
                    <span className="text-green-600 dark:text-green-400 text-[11px] font-medium flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                      连通正常
                    </span>
                  </div>
                  <p className="text-gray-600 dark:text-gray-400 text-xs mt-1.5 leading-relaxed">{srv.desc}</p>
                  <div className="text-[10px] text-gray-400 font-mono mt-1">
                    脚本: {srv.script}
                  </div>
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    <span className="text-[10px] text-gray-400 font-medium">注册工具:</span>
                    {srv.tools.map((t) => (
                      <span key={t} className="px-1.5 py-0.5 rounded bg-gray-200/70 dark:bg-[#232737] text-gray-700 dark:text-gray-300 font-mono text-[10.5px]">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 底部 */}
        <div className="px-5 py-3 bg-gray-50 dark:bg-[#0e1017] border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <span className="text-[11px] text-gray-400">
            {activeTab === "skills" ? `已挂载 ${skills.length} 项 SOP` : "已连接 2 项后台 MCP 服务"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-900 hover:bg-black dark:bg-[#252a3b] dark:hover:bg-[#2e3449] text-white rounded-xl text-xs font-medium transition cursor-pointer"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  );
};
