import React, { useState, useEffect } from "react";
import { 
  X, 
  Settings, 
  Cpu, 
  ShieldCheck, 
  Info, 
  Plus, 
  Check, 
  Layers,
  Sparkles,
  Type
} from "lucide-react";
import { ModelProvider } from "../types";
import { ConfirmModal } from "./ConfirmModal";
import { LOGO_DATA_URI } from "../assets/logoData";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentModel: string;
  onSaveModel: (m: string) => void;
  onProvidersUpdated?: (providers: ModelProvider[], activeModels: string[]) => void;
  theme?: "light" | "dark";
  onSelectTheme?: (theme: "light" | "dark") => void;
  fontSizeLevel?: number;
  onSelectFontSize?: (level: number) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  currentModel,
  onSaveModel,
  onProvidersUpdated,
  theme = "light",
  onSelectTheme,
  fontSizeLevel = 1,
  onSelectFontSize
}) => {
  if (!isOpen) return null;

  const [activeTab, setActiveTab] = useState<"models" | "security" | "general" | "about">("models");
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [editingProvider, setEditingProvider] = useState<ModelProvider | null>(null);
  const [isAddingCustom, setIsAddingCustom] = useState(false);
  const [pendingDeleteProviderId, setPendingDeleteProviderId] = useState<string | null>(null);

  // 编辑表单字段
  const [formName, setFormName] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formModels, setFormModels] = useState("");
  const [isFormCustom, setIsFormCustom] = useState(true);

  useEffect(() => {
    fetchProviders();
  }, [isOpen]);

  const fetchProviders = () => {
    fetch("http://127.0.0.1:8765/api/models/providers")
      .then((res) => res.json())
      .then((data) => {
        if (data.providers) {
          setProviders(data.providers);
        }
      })
      .catch(() => {});
  };

  const handleOpenEdit = (p: ModelProvider) => {
    setEditingProvider(p);
    setFormName(p.name);
    setFormBaseUrl(p.base_url);
    setFormApiKey(p.api_key || "");
    setFormModels((p.models || []).join(", "));
    setIsFormCustom(Boolean(p.is_custom));
    setIsAddingCustom(false);
  };

  const handleOpenAdd = (isCustom: boolean = true) => {
    setEditingProvider(null);
    setIsAddingCustom(true);
    setFormName(isCustom ? "" : "中转代理服务");
    setFormBaseUrl(isCustom ? "" : "https://api.openai.com/v1");
    setFormApiKey("");
    setFormModels("");
    setIsFormCustom(isCustom);
  };

  const handleSaveProviderForm = () => {
    if (!formName.trim() || !formBaseUrl.trim()) {
      alert("请完整填写提供方名称与接口地址！");
      return;
    }

    const modelsList = formModels
      .split(/[,，\s]+/)
      .map((m) => m.trim())
      .filter(Boolean);

    const payload = {
      id: editingProvider ? editingProvider.id : undefined,
      name: formName.trim(),
      base_url: formBaseUrl.trim(),
      api_key: formApiKey.trim(),
      models: modelsList,
      is_custom: isFormCustom
    };

    fetch("http://127.0.0.1:8765/api/models/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setEditingProvider(null);
          setIsAddingCustom(false);
          fetchProviders();
          if (onProvidersUpdated) {
            onProvidersUpdated(data.providers, data.active_models);
          }
        }
      })
      .catch((err) => {
        alert("保存提供方失败: " + err.message);
      });
  };

  const handleDeleteProvider = (id: string) => {
    setPendingDeleteProviderId(id);
  };

  const handleConfirmDeleteProvider = () => {
    if (!pendingDeleteProviderId) return;
    const id = pendingDeleteProviderId;
    setPendingDeleteProviderId(null);

    fetch(`http://127.0.0.1:8765/api/models/providers/${id}`, {
      method: "DELETE"
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          fetchProviders();
          if (onProvidersUpdated) {
            onProvidersUpdated(data.providers, data.active_models);
          }
        }
      })
      .catch(() => {});
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5">
      {/* 左右结构主容器：宽度减半至约原来的一半 (w-[92vw] max-w-[690px] h-[88vh])，高度不变 */}
      <div className="w-[92vw] max-w-[690px] h-[88vh] max-h-[840px] bg-white dark:bg-[#12141c] rounded-2xl shadow-2xl border border-gray-200 dark:border-[#222634] overflow-hidden flex flex-row animate-in fade-in zoom-in-95 duration-150 select-none transition-colors">
        {/* 1. 左侧导航边栏 (紧凑宽度 w-44，留出主内容空间) */}
        <aside className="w-44 h-full bg-[#f8f9fa] dark:bg-[#0d0f15] border-r border-gray-200/80 dark:border-[#1e222f] flex flex-col justify-between p-3 shrink-0 transition-colors">
          <div>
            {/* 左上角标题与 Logo */}
            <div className="flex items-center gap-2.5 px-3 py-3 mb-3 border-b border-gray-200/60 dark:border-[#1e222f]">
              <img src={LOGO_DATA_URI} alt="super logo" className="w-5 h-5 object-contain" />
              <div className="font-bold text-gray-900 dark:text-white text-sm tracking-tight">系统设置</div>
            </div>

            {/* 垂直导航菜单项 */}
            <nav className="space-y-1.5">
              <button
                type="button"
                onClick={() => { setActiveTab("models"); setEditingProvider(null); setIsAddingCustom(false); }}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer ${
                  activeTab === "models"
                    ? "bg-white dark:bg-[#1a1d27] text-blue-600 dark:text-blue-400 shadow-xs font-semibold border border-transparent dark:border-[#2b3042]"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-200/60 dark:hover:bg-[#161822] hover:text-gray-900 dark:hover:text-gray-200"
                }`}
              >
                <Cpu size={16} className={activeTab === "models" ? "text-blue-600 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"} />
                <span>模型提供方</span>
              </button>

              <button
                type="button"
                onClick={() => { setActiveTab("security"); setEditingProvider(null); setIsAddingCustom(false); }}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer ${
                  activeTab === "security"
                    ? "bg-white dark:bg-[#1a1d27] text-blue-600 dark:text-blue-400 shadow-xs font-semibold border border-transparent dark:border-[#2b3042]"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-200/60 dark:hover:bg-[#161822] hover:text-gray-900 dark:hover:text-gray-200"
                }`}
              >
                <ShieldCheck size={16} className={activeTab === "security" ? "text-blue-600 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"} />
                <span>安全与模式</span>
              </button>

              <button
                type="button"
                onClick={() => { setActiveTab("general"); setEditingProvider(null); setIsAddingCustom(false); }}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer ${
                  activeTab === "general"
                    ? "bg-white dark:bg-[#1a1d27] text-blue-600 dark:text-blue-400 shadow-xs font-semibold border border-transparent dark:border-[#2b3042]"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-200/60 dark:hover:bg-[#161822] hover:text-gray-900 dark:hover:text-gray-200"
                }`}
              >
                <Settings size={16} className={activeTab === "general" ? "text-blue-600 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"} />
                <span>通用设置</span>
              </button>

              <button
                type="button"
                onClick={() => { setActiveTab("about"); setEditingProvider(null); setIsAddingCustom(false); }}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer ${
                  activeTab === "about"
                    ? "bg-white dark:bg-[#1a1d27] text-blue-600 dark:text-blue-400 shadow-xs font-semibold border border-transparent dark:border-[#2b3042]"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-200/60 dark:hover:bg-[#161822] hover:text-gray-900 dark:hover:text-gray-200"
                }`}
              >
                <Info size={16} className={activeTab === "about" ? "text-blue-600 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"} />
                <span>关于 super</span>
              </button>
            </nav>
          </div>

          {/* 左下角关闭设置按钮 */}
          <div className="pt-2 border-t border-gray-200/60 dark:border-[#1e222f] px-1">
            <button
              type="button"
              onClick={onClose}
              className="w-full py-2 bg-white dark:bg-[#1a1d27] hover:bg-gray-100 dark:hover:bg-[#222534] border border-gray-200 dark:border-[#2a2e3f] text-gray-700 dark:text-gray-300 rounded-xl text-xs font-medium transition shadow-2xs cursor-pointer"
            >
              关闭设置
            </button>
          </div>
        </aside>

        {/* 2. 右侧主设置视口区 (自适应宽度，支持全屏展开与和谐深色模式) */}
        <main className="flex-1 h-full flex flex-col min-w-0 bg-white dark:bg-[#12141c] transition-colors">
          {/* 右侧顶部栏 */}
          <div className="h-12 border-b border-gray-100 dark:border-[#1e222f] flex items-center justify-between px-7 shrink-0">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              {activeTab === "models" && "Model Providers Configuration"}
              {activeTab === "security" && "Security & Approval Policy"}
              {activeTab === "general" && "General Settings & Preferences"}
              {activeTab === "about" && "About super HARNESS Desktop"}
            </span>
            <button 
              onClick={onClose} 
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-200 rounded-lg transition cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <X size={16} />
            </button>
          </div>

          {/* 右侧主配置内容 */}
          <div className="flex-1 p-7 overflow-y-auto">
            {activeTab === "models" && (
              <div className="space-y-4 max-w-4xl">
                <div>
                  <h2 className="text-base font-bold text-gray-900 dark:text-white">模型提供方</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    填入各提供方的 API 密钥即可使用其模型，添加后将自动映射到对话切换栏。
                  </p>
                </div>

                {/* 提供方卡片列表 */}
                <div className="space-y-2.5 pt-1">
                  {providers.map((p) => {
                    const isConnected = p.status === "connected";
                    return (
                      <div
                        key={p.id || p.name}
                        className="w-full flex items-center justify-between px-4 py-3 bg-white dark:bg-[#171922] border border-gray-200 dark:border-[#262a38] rounded-xl hover:border-gray-300 dark:hover:border-[#383e54] transition shadow-2xs"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="font-semibold text-gray-900 dark:text-gray-100 text-sm">{p.name}</span>
                          {p.is_custom && (
                            <span className="border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 text-[10px] font-medium px-1.5 py-0.5 rounded">
                              自定义
                            </span>
                          )}
                          <span
                            className={`w-2.5 h-2.5 rounded-full inline-block ${
                              isConnected ? "bg-green-500 shadow-sm" : "bg-red-500"
                            }`}
                            title={isConnected ? "已配置可用" : "未配置 API 密钥"}
                          />
                        </div>

                        <div className="flex items-center gap-3 text-xs">
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(p)}
                            className="text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 font-medium px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-[#202330] transition cursor-pointer"
                          >
                            编辑
                          </button>
                          {p.is_custom && (
                            <button
                              type="button"
                              onClick={() => handleDeleteProvider(p.id)}
                              className="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 font-medium px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-950/30 transition cursor-pointer"
                            >
                              删除
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* 底部添加按钮 */}
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => handleOpenAdd(false)}
                    className="flex items-center justify-center gap-1.5 py-3 border border-dashed border-gray-300 dark:border-[#2f354a] hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 rounded-xl text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 text-xs font-medium transition cursor-pointer"
                  >
                    <Plus size={14} />
                    <span>添加提供方</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenAdd(true)}
                    className="flex items-center justify-center gap-1.5 py-3 border border-dashed border-gray-300 dark:border-[#2f354a] hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 rounded-xl text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 text-xs font-medium transition cursor-pointer"
                  >
                    <Plus size={14} />
                    <span>添加自定义提供方</span>
                  </button>
                </div>

                {/* 展开的提供方编辑/新增表单 */}
                {(editingProvider || isAddingCustom) && (
                  <div className="mt-3 p-4 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl space-y-3 animate-in fade-in duration-100 text-xs">
                    <div className="font-semibold text-gray-800 dark:text-gray-200 text-xs flex items-center justify-between">
                      <span>{editingProvider ? `编辑提供方: ${editingProvider.name}` : "新增自定义模型提供方"}</span>
                      <button
                        type="button"
                        onClick={() => { setEditingProvider(null); setIsAddingCustom(false); }}
                        className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 cursor-pointer"
                      >
                        <X size={14} />
                      </button>
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">提供方名称</label>
                      <input
                        type="text"
                        value={formName}
                        onChange={(e) => setFormName(e.target.value)}
                        placeholder="例如: 中转ai.rjk66.cn 或 DeepSeek"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">接口地址 (Base URL)</label>
                      <input
                        type="text"
                        value={formBaseUrl}
                        onChange={(e) => setFormBaseUrl(e.target.value)}
                        placeholder="例如: https://api.deepseek.com/v1 或 http://127.0.0.1:8045/v1"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">API 密钥 (API Key)</label>
                      <input
                        type="password"
                        value={formApiKey}
                        onChange={(e) => setFormApiKey(e.target.value)}
                        placeholder="sk-..."
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">映射模型列表 (逗号分隔，添加后自动进入切换栏)</label>
                      <input
                        type="text"
                        value={formModels}
                        onChange={(e) => setFormModels(e.target.value)}
                        placeholder="例如: gpt-4o, qwen-max, deepseek-chat"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => { setEditingProvider(null); setIsAddingCustom(false); }}
                        className="px-3 py-1.5 border border-gray-200 dark:border-[#2e344a] text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-[#222534] transition cursor-pointer"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        onClick={handleSaveProviderForm}
                        className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition shadow-xs cursor-pointer"
                      >
                        保存并生效
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "security" && (
              <div className="space-y-4 text-xs max-w-4xl">
                <div>
                  <h2 className="text-base font-bold text-gray-900 dark:text-white">安全与模式</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    管理本地 Shell 执行策略与 Human-in-the-Loop 审批级别。
                  </p>
                </div>

                <div className="p-4 bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl space-y-2">
                  <div className="font-semibold text-blue-900 dark:text-blue-300 flex items-center gap-2">
                    <ShieldCheck size={16} className="text-blue-600 dark:text-blue-400" />
                    <span>AUTO 模式 (全自动执行，默认推荐)</span>
                  </div>
                  <p className="text-blue-700 dark:text-blue-300/80 leading-relaxed text-[11px]">
                    非破坏性操作（读取文件、代码走查、pytest 测试、ripgrep 搜索等）全自动静默放行，无需频繁打扰开发者；对任何包含破坏性删除（如 rm -rf、format）或提权命令均实施强制底层阻断。
                  </p>
                </div>

                <div className="p-4 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl space-y-2">
                  <div className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                    <ShieldCheck size={16} className="text-gray-600 dark:text-gray-400" />
                    <span>ASK 模式 (人工交互审批)</span>
                  </div>
                  <p className="text-gray-500 dark:text-gray-400 leading-relaxed text-[11px]">
                    任何涉及文件写入、代码修改或 Shell 命令下发的工具操作，均会在桌面端弹窗等待用户点击允许。
                  </p>
                </div>
              </div>
            )}

            {activeTab === "general" && (
              <div className="space-y-6 text-xs max-w-4xl">
                <div>
                  <h2 className="text-base font-bold text-gray-900 dark:text-white">通用设置</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    自定义界面外观、字号缩放比例、系统运行参数与注意力预算策略。
                  </p>
                </div>

                {/* 1. 外观主题选择区 (对标需求 4：和谐高品质深色外观) */}
                <div className="space-y-3 pt-1 border-t border-gray-100 dark:border-[#1e222f]">
                  <label className="block text-gray-800 dark:text-gray-200 font-semibold text-xs">界面外观风格</label>
                  <p className="text-[11px] text-gray-400">选择您喜爱的应用主题风格，已适配所有窗口与面板色彩系统。</p>
                  
                  <div className="grid grid-cols-2 gap-4 pt-1">
                    {/* 浅色主题卡片 */}
                    <div
                      onClick={() => onSelectTheme && onSelectTheme("light")}
                      className={`p-4 rounded-xl border-2 cursor-pointer transition flex flex-col justify-between ${
                        theme === "light"
                          ? "border-blue-600 bg-blue-50/40 dark:bg-blue-950/20 shadow-xs"
                          : "border-gray-200 dark:border-[#262a38] hover:border-gray-300 dark:hover:border-[#383e54] bg-white dark:bg-[#171922]"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className="w-3.5 h-3.5 rounded-full border border-gray-300 bg-white" />
                          <span className="font-semibold text-gray-900 dark:text-white text-xs">浅色</span>
                        </div>
                        {theme === "light" && <Check size={14} className="text-blue-600" />}
                      </div>
                      <div className="w-full h-12 rounded-lg bg-[#ffffff] border border-gray-200 p-1.5 flex gap-1.5 items-center">
                        <div className="w-4 h-full bg-[#f8f9fa] rounded border border-gray-100" />
                        <div className="flex-1 space-y-1">
                          <div className="w-3/4 h-2 bg-gray-100 rounded" />
                          <div className="w-1/2 h-2 bg-blue-100 rounded" />
                        </div>
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">浅色 (明快清晰 / 白底)</p>
                    </div>

                    {/* 深色主题卡片 */}
                    <div
                      onClick={() => onSelectTheme && onSelectTheme("dark")}
                      className={`p-4 rounded-xl border-2 cursor-pointer transition flex flex-col justify-between ${
                        theme === "dark"
                          ? "border-blue-600 bg-blue-50/20 dark:bg-blue-950/30 shadow-xs"
                          : "border-gray-200 dark:border-[#262a38] hover:border-gray-300 dark:hover:border-[#383e54] bg-white dark:bg-[#171922]"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className="w-3.5 h-3.5 rounded-full border border-gray-600 bg-[#0f1117]" />
                          <span className="font-semibold text-gray-900 dark:text-white text-xs">深色</span>
                        </div>
                        {theme === "dark" && <Check size={14} className="text-blue-600" />}
                      </div>
                      <div className="w-full h-12 rounded-lg bg-[#0f1117] border border-[#2b3042] p-1.5 flex gap-1.5 items-center">
                        <div className="w-4 h-full bg-[#171922] rounded border border-[#2b3042]" />
                        <div className="flex-1 space-y-1">
                          <div className="w-3/4 h-2 bg-gray-700 rounded" />
                          <div className="w-1/2 h-2 bg-blue-500/40 rounded" />
                        </div>
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">深色 (沉浸护眼深黑)</p>
                    </div>
                  </div>
                </div>

                {/* 2. 字体大小左右滑动设置 (对标需求 5：初始值默认已加大一号，可左右滑动无级缩放) */}
                <div className="space-y-3 pt-3 border-t border-gray-100 dark:border-[#1e222f]">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-1.5 font-semibold text-gray-800 dark:text-gray-200 text-xs">
                        <Type size={14} className="text-blue-600 dark:text-blue-400" />
                        <span>界面字体大小</span>
                      </div>
                      <p className="text-[11px] text-gray-400 mt-0.5">
                        滑动调整全桌面界面的字体大小，当前默认字号已整体放大一档以优化阅读体验。
                      </p>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 shrink-0">
                      {fontSizeLevel === 0 && "小 (标准)"}
                      {fontSizeLevel === 1 && "默认 (推荐 · 已加大)"}
                      {fontSizeLevel === 2 && "中 (舒适阅读)"}
                      {fontSizeLevel === 3 && "大 (大字清晰)"}
                      {fontSizeLevel === 4 && "特大 (超大)"}
                    </span>
                  </div>

                  {/* 滑动滑块条 */}
                  <div className="p-3 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl space-y-2">
                    <input
                      type="range"
                      min={0}
                      max={4}
                      step={1}
                      value={fontSizeLevel}
                      onChange={(e) => onSelectFontSize && onSelectFontSize(Number(e.target.value))}
                      className="w-full h-2 bg-gray-200 dark:bg-[#2b3042] rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <div className="flex justify-between text-[11px] text-gray-400 dark:text-gray-500 font-medium px-0.5 select-none">
                      <span className={fontSizeLevel === 0 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>小</span>
                      <span className={fontSizeLevel === 1 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>默认</span>
                      <span className={fontSizeLevel === 2 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>中</span>
                      <span className={fontSizeLevel === 3 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>大</span>
                      <span className={fontSizeLevel === 4 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>特大</span>
                    </div>
                  </div>
                </div>

                {/* 3. 模型与预算参数 */}
                <div className="space-y-3 pt-3 border-t border-gray-100 dark:border-[#1e222f]">
                  <div>
                    <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">当前默认激活推理模型</label>
                    <div className="px-3 py-2 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl font-mono text-gray-800 dark:text-gray-200">
                      {currentModel}
                    </div>
                  </div>

                  <div>
                    <label className="block text-gray-700 dark:text-gray-300 font-medium mb-1">上下文注意力预算水位</label>
                    <div className="px-3 py-2 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl text-gray-600 dark:text-gray-300">
                      200,000 Tokens 基线预算 · 弹性最高支持 500,000 Tokens
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "about" && (
              <div className="space-y-4 text-xs max-w-4xl">
                <div className="flex items-center gap-3">
                  <img src={LOGO_DATA_URI} alt="super logo" className="w-10 h-10 object-contain" />
                  <div>
                    <h2 className="text-base font-bold text-gray-900 dark:text-white">super HARNESS 桌面客户端</h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400">版本 v5.7.4 · DeepSeek Harness 架构增强版</p>
                  </div>
                </div>

                <div className="p-4 bg-gray-50 dark:bg-[#181a24] border border-gray-200 dark:border-[#262a38] rounded-xl space-y-2 text-gray-600 dark:text-gray-300">
                  <p>super HARNESS 是专为智能体工程化研发打造的深度强化工作站。</p>
                  <p>支持多项目工作区并行隔离、自动化工具执行与长程注意力上下文管理。</p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
      {/* 提供方删除桌面端确认弹窗 (对标图一圆角样式) */}
      <ConfirmModal
        isOpen={Boolean(pendingDeleteProviderId)}
        title="删除模型提供方"
        message="确定要删除该提供方配置吗？删除后此模型将从对话切换栏中移除。"
        confirmText="确定删除"
        danger={true}
        onConfirm={handleConfirmDeleteProvider}
        onCancel={() => setPendingDeleteProviderId(null)}
      />
    </div>
  );
};
