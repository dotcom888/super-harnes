import React, { useState, useEffect } from "react";
import {
  X,
  RefreshCw,
  Download, 
  Settings, 
  Cpu, 
  ShieldCheck, 
  Info, 
  Plus, 
  Check, 
  Layers,
  Sparkles,
  Type,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  AlertCircle
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
  initialTab?: "models" | "security" | "general" | "about";
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
  onSelectFontSize,
  initialTab = "models"
}) => {
  if (!isOpen) return null;

  const [activeTab, setActiveTab] = useState<"models" | "security" | "general" | "about">("models");
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [editingProvider, setEditingProvider] = useState<ModelProvider | null>(null);
  const [isAddingCustom, setIsAddingCustom] = useState(false);
  const [pendingDeleteProviderId, setPendingDeleteProviderId] = useState<string | null>(null);

  // 版本检测状态
  const [checkVersionStatus, setCheckVersionStatus] = useState<"idle" | "checking" | "latest" | "has_update" | "error">("idle");
  const [latestVersion, setLatestVersion] = useState<string>("");
  const [releaseUrl, setReleaseUrl] = useState<string>("https://github.com/dotcom888/super-harnes/releases");
  const [downloadAssetUrl, setDownloadAssetUrl] = useState<string>("");
  const [updateNote, setUpdateNote] = useState<string>("");

    // 自动检测版本 (当切换或打开“关于 super”时自动执行一次并呈现动态效果)
  useEffect(() => {
    if (isOpen && activeTab === "about") {
      handleCheckVersion();
    }
  }, [isOpen, activeTab]);

  const handleCheckVersion = async () => {
    setCheckVersionStatus("checking");
    const startTime = Date.now();
    try {
      const res = await fetch("https://api.github.com/repos/dotcom888/super-harnes/releases/latest", {
        headers: { Accept: "application/vnd.github.v3+json" }
      });
      if (!res.ok) {
        throw new Error("HTTP " + res.status);
      }
      const data = await res.json();
      const tag = (data.tag_name || data.name || "").trim();
      const currentVer = "v5.7.6";
      setLatestVersion(tag || "未知");
      const htmlUrl = data.html_url || "https://github.com/dotcom888/super-harnes/releases";
      setReleaseUrl(htmlUrl);
      setUpdateNote(data.body ? data.body.slice(0, 180) : "");

      const exeAsset = (data.assets || []).find((a) =>
        a.name && (a.name.endsWith(".exe") || a.name.endsWith(".zip"))
      );
      if (exeAsset) {
        setDownloadAssetUrl(exeAsset.browser_download_url);
      } else {
        setDownloadAssetUrl(htmlUrl);
      }

      const cleanTag = tag.replace(/^v/i, "");
      const cleanCurrent = currentVer.replace(/^v/i, "");

      // 确保至少有 500ms 动态转圈过程，提供清晰视觉反馈
      const elapsed = Date.now() - startTime;
      if (elapsed < 500) {
        await new Promise((r) => setTimeout(r, 500 - elapsed));
      }

      if (cleanTag === cleanCurrent || !cleanTag) {
        setCheckVersionStatus("latest");
      } else {
        setCheckVersionStatus("has_update");
      }
    } catch (e) {
      setCheckVersionStatus("error");
    }
  };

  const handleOpenRelease = (url) => {
    const target = url || downloadAssetUrl || releaseUrl;
    if (window.electronAPI && window.electronAPI.openExternal) {
      window.electronAPI.openExternal(target);
    } else {
      window.open(target, "_blank");
    }
  };

  // 编辑表单字段
  const [formName, setFormName] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formModels, setFormModels] = useState("");
  const [formProtocol, setFormProtocol] = useState<string>("openai_chat");
  const [isFormCustom, setIsFormCustom] = useState(true);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [validationError, setValidationError] = useState("");
  const [saveSuccessMsg, setSaveSuccessMsg] = useState("");

  useEffect(() => {
    fetchProviders();
    if (isOpen && initialTab) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

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
    setFormProtocol(p.protocol || "openai_chat");
    setIsFormCustom(Boolean(p.is_custom));
    setIsAddingCustom(false);
    setShowApiKey(false);
    setTestResult(null);
    setValidationError("");
    setSaveSuccessMsg("");
  };

  const handleOpenAdd = () => {
    setEditingProvider(null);
    setIsAddingCustom(true);
    setFormName("");
    setFormBaseUrl("");
    setFormApiKey("");
    setFormModels("");
    setFormProtocol("openai_chat");
    setIsFormCustom(true);
    setShowApiKey(false);
    setTestResult(null);
    setValidationError("");
    setSaveSuccessMsg("");
  };

  // 连通性测试
  const handleTestConnection = async () => {
    setValidationError("");
    const trimmedUrl = formBaseUrl.trim().replace(/\/+$/, "");
    const trimmedKey = formApiKey.trim();
    if (!trimmedUrl) {
      setValidationError("请先填写接口地址 (Base URL)");
      return;
    }
    if (!trimmedKey) {
      setValidationError("请先填写 API 密钥 (API Key)");
      return;
    }

    const firstModel = formModels.split(/[,，\s]+/).map(m => m.trim()).filter(Boolean)[0] || "";

    setIsTesting(true);
    setTestResult(null);

    try {
      const res = await fetch("http://127.0.0.1:8765/api/models/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: trimmedUrl,
          api_key: trimmedKey,
          model: firstModel || undefined,
          protocol: formProtocol
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTestResult({ success: true, message: data.message || "接口连通正常，鉴权通过！" });
      } else {
        setTestResult({ success: false, message: data.error || data.detail || "连接失败，请检查 Base URL 与 API Key" });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: "请求服务失败: " + err.message });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveProviderForm = () => {
    setValidationError("");
    setSaveSuccessMsg("");

    const name = formName.trim();
    const baseUrl = formBaseUrl.trim().replace(/\/+$/, "");
    const apiKey = formApiKey.trim();
    const modelsList = formModels
      .split(/[,，\s]+/)
      .map((m) => m.trim())
      .filter(Boolean);

    // 严密字段校验 (对标需求 2)
    if (!name) {
      setValidationError("请填写提供方名称（例如: DeepSeek）");
      return;
    }
    if (!baseUrl) {
      setValidationError("请填写接口地址 Base URL（例如: https://api.deepseek.com/v1）");
      return;
    }
    if (!baseUrl.startsWith("http://") && !baseUrl.startsWith("https://")) {
      setValidationError("接口地址格式无效，必须以 http:// 或 https:// 开头");
      return;
    }
    if (!apiKey) {
      setValidationError("请填写 API 密钥 (API Key)");
      return;
    }
    if (modelsList.length === 0) {
      setValidationError("请至少填写一个映射模型名称（例如: deepseek-chat, deepseek-reasoner）");
      return;
    }

    const payload = {
      id: editingProvider ? editingProvider.id : undefined,
      name: name,
      base_url: baseUrl,
      api_key: apiKey,
      models: modelsList,
      protocol: formProtocol,
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
          setSaveSuccessMsg("保存成功！已更新提供方并同步模型。");
          fetchProviders();
          if (onProvidersUpdated) {
            onProvidersUpdated(data.providers, data.active_models);
          }
          setTimeout(() => {
            setEditingProvider(null);
            setIsAddingCustom(false);
            setSaveSuccessMsg("");
          }, 1200);
        }
      })
      .catch((err) => {
        setValidationError("保存提供方失败: " + err.message);
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
              type="button"
              onClick={onClose} 
              className="w-9 h-9 flex items-center justify-center text-gray-400 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100 rounded-xl transition cursor-pointer hover:bg-gray-100 dark:hover:bg-[#20222f] titlebar-no-drag z-30"
              title="关闭设置"
            >
              <X size={18} />
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
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/40">
                            {p.protocol === "openai_responses" ? "/v1/responses" : p.protocol === "anthropic_messages" ? "/v1/messages" : p.protocol === "gemini_v1beta" ? "/v1beta" : "/chat/completions"}
                          </span>
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
                          <button
      type="button"
      onClick={() => handleDeleteProvider(p.id)}
      className="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 font-medium px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-950/30 transition cursor-pointer"
    >
      删除
    </button>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* 底部添加按钮：删除冗余的“添加提供方”，保留单体清晰的自定义添加按钮 (对标需求 1) */}
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={handleOpenAdd}
                    className="w-full flex items-center justify-center gap-1.5 py-3 border border-dashed border-gray-300 dark:border-[#2f354a] hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 rounded-xl text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 text-xs font-medium transition cursor-pointer"
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
                        placeholder="例如: DeepSeek"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">接口地址 (Base URL)</label>
                      <input
                        type="text"
                        value={formBaseUrl}
                        onChange={(e) => setFormBaseUrl(e.target.value)}
                        placeholder="例如: https://api.deepseek.com/v1"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1 flex items-center justify-between">
                        <span>接口协议 / 报文格式 (Protocol)</span>
                        <span className="text-[11px] text-blue-600 dark:text-blue-400 font-normal">默认: /chat/completions</span>
                      </label>
                      <select
                        value={formProtocol}
                        onChange={(e) => setFormProtocol(e.target.value)}
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none cursor-pointer"
                      >
                        <option value="openai_chat">OpenAI 兼容 (/chat/completions) (推荐)</option>
                        <option value="openai_responses">OpenAI Responses (/v1/responses)</option>
                        <option value="anthropic_messages">Anthropic Claude (/v1/messages)</option>
                        <option value="gemini_v1beta">Google Gemini (/v1beta)</option>
                      </select>
                      <div className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                        市面上绝大多数大模型与中转（DeepSeek、通义千问、Kimi 等）均原生支持 OpenAI /chat/completions。
                      </div>
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">API 密钥 (API Key)</label>
                      <div className="relative flex items-center">
                        <input
                          type={showApiKey ? "text" : "password"}
                          value={formApiKey}
                          onChange={(e) => setFormApiKey(e.target.value)}
                          placeholder="sk-..."
                          className="w-full px-3 py-1.5 pr-9 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute right-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer p-0.5"
                          title={showApiKey ? "隐藏密钥" : "显示密钥"}
                        >
                          {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-gray-600 dark:text-gray-400 font-medium mb-1">映射模型列表 (逗号分隔，添加后自动进入切换栏)</label>
                      <input
                        type="text"
                        value={formModels}
                        onChange={(e) => setFormModels(e.target.value)}
                        placeholder="例如: deepseek-chat, deepseek-reasoner"
                        className="w-full px-3 py-1.5 bg-white dark:bg-[#1f2230] border border-gray-200 dark:border-[#2e344a] text-gray-900 dark:text-gray-100 rounded-lg focus:border-blue-500 outline-none font-mono"
                      />
                    </div>

                    {/* 校验错误提示条 */}
                    {validationError && (
                      <div className="flex items-center gap-1.5 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/40 rounded-lg text-red-600 dark:text-red-400 text-xs">
                        <AlertCircle size={14} className="shrink-0" />
                        <span>{validationError}</span>
                      </div>
                    )}

                    {/* 测试连通性结果反馈 */}
                    {testResult && (
                      <div className={`flex items-start gap-1.5 p-2 rounded-lg text-xs border ${
                        testResult.success 
                          ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800/40 text-green-700 dark:text-green-400"
                          : "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/40 text-amber-700 dark:text-amber-400"
                      }`}>
                        {testResult.success ? (
                          <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
                        ) : (
                          <AlertCircle size={14} className="shrink-0 mt-0.5" />
                        )}
                        <span className="leading-relaxed">{testResult.message}</span>
                      </div>
                    )}

                    {/* 保存成功动画条 */}
                    {saveSuccessMsg && (
                      <div className="flex items-center gap-1.5 p-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800/40 rounded-lg text-green-700 dark:text-green-400 text-xs animate-in fade-in">
                        <CheckCircle2 size={14} className="shrink-0" />
                        <span className="font-medium">{saveSuccessMsg}</span>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-2">
                      <button
                        type="button"
                        onClick={handleTestConnection}
                        disabled={isTesting}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-blue-200 dark:border-blue-900/50 bg-blue-50/50 dark:bg-blue-900/20 hover:bg-blue-100/70 dark:hover:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
                      >
                        {isTesting && <Loader2 size={13} className="animate-spin" />}
                        <span>{isTesting ? "正在测试..." : "测试连接"}</span>
                      </button>

                      <div className="flex items-center gap-2">
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
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <img src={LOGO_DATA_URI} alt="super logo" className="w-10 h-10 object-contain" />
                    <div>
                      <h2 className="text-base font-bold text-gray-900 dark:text-white">super HARNESS 桌面客户端</h2>
                      <p className="text-xs text-gray-500 dark:text-gray-400">版本 v5.7.6 · DeepSeek Harness 架构增强版</p>
                    </div>
                  </div>

                  {/* 检测版本按钮 (对标图五需求 3) */}
                  <button
                    type="button"
                    onClick={handleCheckVersion}
                    disabled={checkVersionStatus === "checking"}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-[#181a24] hover:bg-gray-50 dark:hover:bg-[#20222f] border border-gray-200 dark:border-[#2b3042] text-gray-700 dark:text-gray-200 rounded-xl text-xs font-medium transition cursor-pointer shadow-2xs shrink-0"
                  >
                    {checkVersionStatus === "checking" ? (
                      <Loader2 size={13} className="animate-spin text-blue-500" />
                    ) : (
                      <RefreshCw size={13} className="text-gray-500 dark:text-gray-400" />
                    )}
                    <span>{checkVersionStatus === "checking" ? "正在检测版本..." : "检测版本"}</span>
                  </button>
                </div>

                {/* 检测结果状态提示卡片 */}
                {checkVersionStatus === "latest" && (
                  <div className="flex items-center gap-2 p-3 bg-emerald-50/80 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40 rounded-xl text-emerald-700 dark:text-emerald-400">
                    <CheckCircle2 size={16} className="shrink-0" />
                    <span className="font-medium">当前已是最新版本 (v5.7.6)，与 GitHub 官方发布版本一致。</span>
                  </div>
                )}

                {checkVersionStatus === "has_update" && (
                  <div className="p-4 bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/40 rounded-xl space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-blue-800 dark:text-blue-300 font-semibold">
                        <Sparkles size={16} />
                        <span>发现新版本: {latestVersion} (当前为 v5.7.6)</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleOpenRelease()}
                        className="flex items-center gap-1.5 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-xs shadow-xs transition cursor-pointer"
                      >
                        <Download size={13} />
                        <span>下载更新安装最新版</span>
                      </button>
                    </div>
                    {updateNote && (
                      <p className="text-[11px] text-blue-900/80 dark:text-blue-300/80 line-clamp-2">
                        更新日志: {updateNote}
                      </p>
                    )}
                  </div>
                )}

                {checkVersionStatus === "error" && (
                  <div className="flex items-center justify-between p-3 bg-amber-50/80 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 rounded-xl text-amber-800 dark:text-amber-300">
                    <div className="flex items-center gap-2">
                      <AlertCircle size={15} className="shrink-0" />
                      <span>检测版本超时或网络未连接，可前往 GitHub Releases 页面查看。</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleOpenRelease("https://github.com/dotcom888/super-harnes/releases")}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline shrink-0"
                    >
                      访问 Releases
                    </button>
                  </div>
                )}

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
