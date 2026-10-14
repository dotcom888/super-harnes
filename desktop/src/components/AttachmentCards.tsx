import React, { useState } from "react";
import { 
  FileText, 
  FileSpreadsheet, 
  Image as ImageIcon, 
  FileCode, 
  File, 
  X, 
  ExternalLink,
  Eye
} from "lucide-react";
import { AttachmentItem } from "../types";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getAttachmentTypeIcon(type: string) {
  switch (type) {
    case "pdf":
      return <FileText size={15} className="text-red-500 shrink-0" />;
    case "word":
      return <FileText size={15} className="text-blue-500 shrink-0" />;
    case "excel":
      return <FileSpreadsheet size={15} className="text-emerald-500 shrink-0" />;
    case "image":
      return <ImageIcon size={15} className="text-purple-500 shrink-0" />;
    case "text":
      return <FileCode size={15} className="text-indigo-500 shrink-0" />;
    default:
      return <File size={15} className="text-gray-500 shrink-0" />;
  }
}

export function getAttachmentTypeBadge(type: string): { label: string; colorClass: string } {
  switch (type) {
    case "pdf":
      return { label: "PDF", colorClass: "bg-red-50 text-red-600 border-red-200 dark:bg-red-950/40 dark:text-red-400" };
    case "word":
      return { label: "DOC", colorClass: "bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400" };
    case "excel":
      return { label: "XLS", colorClass: "bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400" };
    case "image":
      return { label: "IMG", colorClass: "bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400" };
    case "text":
      return { label: "TXT", colorClass: "bg-indigo-50 text-indigo-600 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400" };
    default:
      return { label: "FILE", colorClass: "bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400" };
  }
}

/** 输入框待发送卡片 (固定统一尺寸 210x48，长文件名省略截断，保持大小严格一致) */
export const PendingAttachmentChip: React.FC<{
  attachment: AttachmentItem;
  onRemove: (id: string) => void;
}> = ({ attachment, onRemove }) => {
  const badge = getAttachmentTypeBadge(attachment.type);

  return (
    <div className="flex items-center gap-2 px-2.5 py-1.5 w-[210px] max-w-[210px] min-w-[210px] h-[48px] bg-gray-50 dark:bg-[#20232e] border border-gray-200 dark:border-gray-700/80 rounded-xl text-xs shadow-2xs group relative shrink-0 overflow-hidden select-none">
      {/* 缩略图或类型徽标 (固定 32x32) */}
      {attachment.type === "image" && (attachment.dataUrl || attachment.url) ? (
        <img 
          src={attachment.dataUrl || attachment.url} 
          alt={attachment.name} 
          className="w-8 h-8 object-cover rounded-lg border border-gray-200 dark:border-gray-700 shrink-0" 
        />
      ) : (
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-mono font-bold text-[10px] border shrink-0 ${badge.colorClass}`}>
          {badge.label}
        </div>
      )}

      <div className="flex flex-col min-w-0 flex-1 pr-1 overflow-hidden">
        <span className="truncate block font-medium text-gray-800 dark:text-gray-200 text-xs" title={attachment.name}>
          {attachment.name}
        </span>
        <span className="text-[10px] text-gray-400 font-mono truncate">
          {formatFileSize(attachment.size)}
        </span>
      </div>

      <button
        type="button"
        onClick={() => onRemove(attachment.id)}
        className="p-1 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 transition cursor-pointer shrink-0"
        title="移除此附件"
      >
        <X size={13} />
      </button>
    </div>
  );
};

/** 聊天气泡内展示的附件卡片 (固定统一规格 220x52，长文件名自动截断，对标图二保持大小一致) */
export const ChatAttachmentItemCard: React.FC<{
  attachment: AttachmentItem;
}> = ({ attachment }) => {
  const [previewOpen, setPreviewOpen] = useState(false);
  const badge = getAttachmentTypeBadge(attachment.type);

  return (
    <>
      <div className="flex items-center gap-2.5 px-3 py-2 w-[220px] max-w-[220px] min-w-[220px] h-[52px] bg-white/95 dark:bg-[#1a1d27] border border-gray-200/90 dark:border-gray-700/80 rounded-xl text-xs shadow-2xs hover:shadow-xs transition select-none shrink-0 overflow-hidden">
        {/* 缩略图或类型徽标 (固定 36x36 规格) */}
        {attachment.type === "image" && (attachment.dataUrl || attachment.url) ? (
          <div 
            onClick={() => setPreviewOpen(true)}
            className="relative cursor-pointer group shrink-0 w-9 h-9"
            title="点击查看原图"
          >
            <img 
              src={attachment.dataUrl || attachment.url} 
              alt={attachment.name} 
              className="w-9 h-9 object-cover rounded-lg border border-gray-200 dark:border-gray-700" 
            />
            <div className="absolute inset-0 bg-black/30 rounded-lg opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition">
              <Eye size={12} />
            </div>
          </div>
        ) : (
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-mono font-bold text-[11px] border shrink-0 ${badge.colorClass}`}>
            {badge.label}
          </div>
        )}

        <div className="flex flex-col min-w-0 flex-1 pr-1 overflow-hidden">
          <span className="truncate block font-medium text-gray-850 dark:text-gray-100 text-xs" title={attachment.name}>
            {attachment.name}
          </span>
          <div className="flex items-center gap-1.5 text-[10px] text-gray-400 font-mono mt-0.5 truncate">
            <span>{formatFileSize(attachment.size)}</span>
            <span className="text-gray-300 dark:text-gray-600">·</span>
            <span className="capitalize">{attachment.type}</span>
          </div>
        </div>

        {attachment.url && (
          <a
            href={attachment.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition cursor-pointer shrink-0"
            title="查看或下载文件"
          >
            <ExternalLink size={13} />
          </a>
        )}
      </div>

      {/* 图片放大预览模态框 */}
      {previewOpen && (
        <div 
          className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4 backdrop-blur-xs cursor-pointer animate-in fade-in duration-150"
          onClick={() => setPreviewOpen(false)}
        >
          <div className="relative max-w-4xl max-h-[85vh] flex flex-col items-center bg-transparent" onClick={(e) => e.stopPropagation()}>
            <img 
              src={attachment.dataUrl || attachment.url} 
              alt={attachment.name} 
              className="max-h-[80vh] max-w-full rounded-2xl object-contain shadow-2xl border border-white/10"
            />
            <div className="mt-2.5 px-4 py-1.5 bg-black/60 backdrop-blur-md rounded-full text-white text-xs flex items-center gap-3">
              <span className="max-w-xs truncate">{attachment.name}</span>
              <span className="text-white/60 font-mono">{formatFileSize(attachment.size)}</span>
              <button 
                onClick={() => setPreviewOpen(false)} 
                className="hover:text-red-400 cursor-pointer ml-2"
                title="关闭"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
