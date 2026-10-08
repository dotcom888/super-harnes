import React from "react";
import { ShieldAlert, Check, X, ShieldCheck } from "lucide-react";

interface ApprovalModalProps {
  request: { ticket_id: string; command: string; reason: string } | null;
  onApprove: (ticketId: string, trustSession: boolean) => void;
  onReject: (ticketId: string) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({ request, onApprove, onReject }) => {
  if (!request) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-[500px] bg-white rounded-2xl shadow-2xl border border-yellow-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-5 py-3.5 bg-amber-50 border-b border-amber-100 flex items-center gap-2 text-amber-800">
          <ShieldAlert size={18} className="text-amber-600" />
          <span className="font-semibold text-sm">敏感终端命令审批请求</span>
        </div>

        <div className="p-5 text-xs space-y-3">
          <p className="text-gray-600">智能体申请在本地环境中执行以下 Shell 命令：</p>
          <div className="p-3 bg-gray-900 text-gray-100 rounded-xl font-mono text-xs overflow-x-auto">
            {request.command}
          </div>
          {request.reason && (
            <p className="text-gray-500">
              <span className="font-semibold text-gray-700">审批原因: </span>
              {request.reason}
            </p>
          )}
        </div>

        <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 flex justify-end gap-2 text-xs">
          <button
            onClick={() => onReject(request.ticket_id)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 border border-gray-300 text-gray-700 hover:bg-gray-100 rounded-xl font-medium transition"
          >
            <X size={14} />
            <span>拒绝执行</span>
          </button>
          <button
            onClick={() => onApprove(request.ticket_id, false)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-medium transition shadow-sm"
          >
            <Check size={14} />
            <span>单次批准</span>
          </button>
          <button
            onClick={() => onApprove(request.ticket_id, true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition shadow-sm"
          >
            <ShieldCheck size={14} />
            <span>信任本会话</span>
          </button>
        </div>
      </div>
    </div>
  );
};
