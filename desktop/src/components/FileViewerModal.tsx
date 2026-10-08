import React, { useEffect, useState } from "react";
import { X, FileCode, Copy, Check } from "lucide-react";

interface FileViewerModalProps {
  filePath: string | null;
  onClose: () => void;
}

export const FileViewerModal: React.FC<FileViewerModalProps> = ({ filePath, onClose }) => {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!filePath) return;
    setLoading(true);
    fetch(`http://127.0.0.1:8765/api/file/read?path=${encodeURIComponent(filePath)}`)
      .then((res) => res.json())
      .then((data) => {
        setContent(data.content || "（文件内容为空）");
        setLoading(false);
      })
      .catch((err) => {
        setContent(`读取文件失败: ${err.message}`);
        setLoading(false);
      });
  }, [filePath]);

  if (!filePath) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = content.split("\n");

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex justify-end transition-opacity">
      <div className="w-[680px] h-full bg-white shadow-2xl flex flex-col border-l border-gray-200 animate-in slide-in-from-right duration-200">
        {/* 顶部标题栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-2 truncate">
            <FileCode size={16} className="text-blue-600 shrink-0" />
            <span className="font-mono text-xs font-semibold text-gray-800 truncate">{filePath}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-200 rounded transition"
              title="复制全部代码"
            >
              {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
            </button>
            <button
              onClick={onClose}
              className="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-200 rounded transition"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* 代码内容区域 */}
        <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-[#f8f9fa] leading-relaxed select-text">
          {loading ? (
            <div className="text-gray-400 py-10 text-center">正在加载代码文件...</div>
          ) : (
            <table className="w-full border-collapse">
              <tbody>
                {lines.map((line, idx) => (
                  <tr key={idx} className="hover:bg-blue-50/50">
                    <td className="text-gray-400 select-none pr-4 text-right w-10 align-top text-[11px]">
                      {idx + 1}
                    </td>
                    <td className="text-gray-800 whitespace-pre font-mono">{line}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
