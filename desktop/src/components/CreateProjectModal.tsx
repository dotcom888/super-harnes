import React, { useState } from "react";
import { Folder, FolderPlus, X, Check, HardDrive, RefreshCw } from "lucide-react";

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (name: string, path: string) => Promise<void> | void;
}

export const CreateProjectModal: React.FC<CreateProjectModalProps> = ({
  isOpen,
  onClose,
  onCreate
}) => {
  const [projectName, setProjectName] = useState<string>("");
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");

  if (!isOpen) return null;

  // 调起系统原生文件夹选择器
  const handleSelectFolder = async () => {
    setErrorMsg("");
    const electronAPI = (window as any).electronAPI;
    let chosenDir: string | null = null;

    if (electronAPI?.selectDirectory) {
      try {
        chosenDir = await electronAPI.selectDirectory();
      } catch (e) {
        console.error("Failed to select directory:", e);
      }
    } else {
      chosenDir = window.prompt("请输入本地项目文件夹绝对路径:");
    }

    if (chosenDir) {
      setSelectedPath(chosenDir);
      // 若用户尚未输入项目名称，自动从路径最后一段提取默认名称
      if (!projectName.trim()) {
        const segments = chosenDir.replace(/\\/g, "/").split("/").filter(Boolean);
        if (segments.length > 0) {
          setProjectName(segments[segments.length - 1]);
        }
      }
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanName = projectName.trim();
    const cleanPath = selectedPath.trim();

    if (!cleanName) {
      setErrorMsg("请填写工作区名称");
      return;
    }
    if (!cleanPath) {
      setErrorMsg("请选择本地源码目录");
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg("");
      await onCreate(cleanName, cleanPath);
      // 清空状态并关闭
      setProjectName("");
      setSelectedPath("");
      onClose();
    } catch (err: any) {
      setErrorMsg(err?.message || "创建工作区失败，请检查路径是否有效");
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = Boolean(projectName.trim() && selectedPath.trim()) && !isSubmitting;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 select-none">
      <div className="w-[520px] bg-white dark:bg-[#181a24] rounded-2xl shadow-2xl border border-gray-200 dark:border-[#2a2e3f] overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col">
        {/* 1. 顶部标题栏 */}
        <div className="px-5 py-4 flex items-center justify-between border-b border-gray-100 dark:border-[#252837]">
          <div className="flex items-center gap-2">
            <Folder className="text-blue-600 dark:text-blue-400" size={20} />
            <span className="font-bold text-gray-900 dark:text-white text-base">
              新建项目工作区
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-[#252835] transition cursor-pointer"
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>

        {/* 2. 主体表单区 (对标图三样式) */}
        <div className="p-6 space-y-5">
          {/* 错误提示 */}
          {errorMsg && (
            <div className="p-2.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
              {errorMsg}
            </div>
          )}

          {/* 工作区名称输入框 */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-gray-700 dark:text-gray-300">
              工作区名称
            </label>
            <div className="relative flex items-center">
              <div className="absolute left-3.5 text-gray-400 dark:text-gray-500 pointer-events-none">
                <Folder size={16} />
              </div>
              <input
                type="text"
                value={projectName}
                onChange={(e) => {
                  setProjectName(e.target.value);
                  setErrorMsg("");
                }}
                placeholder="输入工作区名称 (如：ECoHarvest、MyProject)"
                className="w-full pl-10 pr-3.5 py-2.5 bg-white dark:bg-[#11131a] border border-blue-400/80 dark:border-blue-500/80 rounded-xl text-xs text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/20 font-medium transition shadow-xs"
                autoFocus
              />
            </div>
          </div>

          {/* 本地源码目录 (对标图三 Source folders 卡片) */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-gray-700 dark:text-gray-300">
              本地源码目录
            </label>
            <div className="p-5 rounded-2xl border border-gray-200 dark:border-[#2a2e3f] bg-gray-50/70 dark:bg-[#13151e] flex flex-col items-center justify-center min-h-[120px] transition">
              {selectedPath ? (
                <div className="w-full flex flex-col gap-2.5">
                  <div className="flex items-start gap-2.5 p-3 bg-white dark:bg-[#1c1f2b] rounded-xl border border-blue-200 dark:border-blue-900/60 shadow-xs">
                    <HardDrive className="text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" size={16} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-gray-400 dark:text-gray-500 font-semibold uppercase tracking-wider">
                        已选择路径
                      </div>
                      <div className="text-xs font-mono text-gray-800 dark:text-gray-200 truncate font-semibold" title={selectedPath}>
                        {selectedPath}
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleSelectFolder}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <span>更换文件夹</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">
                    在电脑上添加文件夹
                  </span>
                  <button
                    type="button"
                    onClick={handleSelectFolder}
                    className="flex items-center gap-1.5 px-4 py-2 bg-white dark:bg-[#202330] border border-gray-200 dark:border-gray-700 hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-[#252a3a] text-gray-700 dark:text-gray-200 text-xs font-semibold rounded-xl shadow-xs transition cursor-pointer"
                  >
                    <FolderPlus size={15} className="text-blue-600 dark:text-blue-400" />
                    <span>添加 / 选择文件夹</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 3. 底部操作按钮 */}
        <div className="px-6 py-4 bg-gray-50/60 dark:bg-[#12141c] border-t border-gray-100 dark:border-[#222533] flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#252838] rounded-xl text-xs font-semibold transition cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => handleSubmit()}
            disabled={!canSubmit}
            className={`flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer ${
              canSubmit
                ? "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white"
                : "bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed"
            }`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span>创建中...</span>
              </>
            ) : (
              <>
                <Check size={14} />
                <span>创建工作区</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
