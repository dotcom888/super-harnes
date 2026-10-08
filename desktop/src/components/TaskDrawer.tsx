import React, { useState } from "react";
import { CheckSquare, ChevronUp, ChevronDown, Check, Circle } from "lucide-react";
import { TaskItem } from "../types";

interface TaskDrawerProps {
  tasks: TaskItem[];
}

export const TaskDrawer: React.FC<TaskDrawerProps> = ({ tasks }) => {
  const [open, setOpen] = useState(false);
  const completedCount = tasks.filter(t => t.completed).length;

  return (
    <div className="w-full my-3">
      {/* 折叠触发条 (对标图二: 📋 任务 7 已完成 ^) */}
      <div
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3.5 py-2 bg-gray-100 hover:bg-gray-150 border border-gray-200 rounded-xl cursor-pointer transition select-none text-xs text-gray-700"
      >
        <div className="flex items-center gap-2">
          <CheckSquare size={14} className="text-gray-600" />
          <span className="font-medium">任务</span>
          <span className="text-gray-500">{completedCount} 已完成</span>
        </div>
        {open ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronUp size={14} className="text-gray-500" />}
      </div>

      {/* 展开的任务清单详情 */}
      {open && (
        <div className="mt-1.5 p-3 bg-white border border-gray-200 rounded-xl shadow-xs space-y-1.5 text-xs">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-center gap-2 text-gray-700">
              {task.completed ? (
                <span className="w-4 h-4 rounded bg-green-500 text-white flex items-center justify-center shrink-0">
                  <Check size={11} strokeWidth={3} />
                </span>
              ) : (
                <Circle size={14} className="text-gray-400 shrink-0" />
              )}
              <span className={task.completed ? "line-through text-gray-400" : "font-normal"}>
                {task.title}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
