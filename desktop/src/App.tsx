import React, { useState, useEffect, useLayoutEffect, useRef } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { WindowControls } from "./components/WindowControls";
import { EmptyState } from "./components/EmptyState";
import { ActionItem } from "./components/ActionItem";
import { ChatMessage } from "./components/ChatMessage";
import { TaskDrawer } from "./components/TaskDrawer";
import { BottomInput } from "./components/BottomInput";
import { FileViewerModal } from "./components/FileViewerModal";
import { SettingsModal } from "./components/SettingsModal";
import { PluginsModal } from "./components/PluginsModal";
import { ApprovalModal } from "./components/ApprovalModal";
import { ConfirmModal } from "./components/ConfirmModal";
import { SessionInfo, ProjectInfo, ToolAction, TaskItem, TurnData, TelemetryMetrics, TrajectoryStep, AttachmentItem } from "./types";
import { TrajectoryTimeline } from "./components/TrajectoryTimeline";
import { LOGO_DATA_URI } from "./assets/logoData";

// 生成复合工程与会话键，保证跨项目及同项目多会话 100% 独立隔离
const getSessionKey = (proj: string, sid: string) => `${proj || "default"}:${sid || "default"}`;

export const App: React.FC = () => {
  // 侧边栏与弹窗状态
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "trace">("chat");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showPlugins, setShowPlugins] = useState(false);
  const [approvalReq, setApprovalReq] = useState<{ ticket_id: string; command: string; reason: string } | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  } | null>(null);

  // 多工程工作区状态 (扫描包含 4 个项目的全部历史消息)
  const [projectName, setProjectName] = useState("super-harnes");
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("default");
  const [sessionTitle, setSessionTitle] = useState("默认会话");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);

  // 模型状态 (仅同步有效配置的模型，支持自定义映射)
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelProviders, setModelProviders] = useState<Record<string, string>>({});
  const [currentModel, setCurrentModel] = useState("");
  const [settingsInitialTab, setSettingsInitialTab] = useState<"models" | "security" | "general" | "about">("models");
  const [modeName, setModeName] = useState("AUTO 模式");

  // 外观主题状态 (浅色为当前默认背景色，深色为护眼深黑)
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    return (localStorage.getItem("super_theme") as "light" | "dark") || "light";
  });

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("super_theme", theme);
  }, [theme]);

  // 界面字号多级控制 (0: 小-15px, 1: 默认-17px, 2: 中-18.5px, 3: 大-20px, 4: 特大-21.5px)
  const FONT_SIZES = [15, 17, 18.5, 20, 21.5];
  const [fontSizeLevel, setFontSizeLevel] = useState<number>(() => {
    const saved = localStorage.getItem("super_font_size");
    return saved !== null ? Number(saved) : 1; // 初始值为 1 (默认放大一档)
  });

  useEffect(() => {
    const size = FONT_SIZES[fontSizeLevel] || 17;
    document.documentElement.style.fontSize = `${size}px`;
    localStorage.setItem("super_font_size", String(fontSizeLevel));
  }, [fontSizeLevel]);

  // 多会话独立状态隔离字典 (按照 project:session_id 绝对隔离)
  const [hasStarted, setHasStarted] = useState(false);
  const [isWsConnected, setIsWsConnected] = useState(true);
  const [sessionTurnsMap, setSessionTurnsMap] = useState<Record<string, TurnData[]>>({});
  const [sessionActionsMap, setSessionActionsMap] = useState<Record<string, ToolAction[]>>({});
  const [sessionThoughtMap, setSessionThoughtMap] = useState<Record<string, string>>({});
  const [runningSessions, setRunningSessions] = useState<Record<string, boolean>>({});
  const [draftPrompt, setDraftPrompt] = useState("");
  const [tasks, setTasks] = useState<TaskItem[]>([]);

  // 当前激活会话的复合键与派生状态
  const currentSessionKey = getSessionKey(projectName, activeSessionId);
  const turns = sessionTurnsMap[currentSessionKey] || [];
  const actions = sessionActionsMap[currentSessionKey] || [];
  const thoughtText = sessionThoughtMap[currentSessionKey] || "";
  const isCurrentSessionLoading = Boolean(runningSessions[currentSessionKey]);

  // 同步 Refs 供长连 WebSocket 内部安全读取活跃态，消除闭包陈旧
  const activeSessionIdRef = useRef(activeSessionId);
  const projectNameRef = useRef(projectName);
  const runningSessionsRef = useRef(runningSessions);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  useEffect(() => {
    projectNameRef.current = projectName;
  }, [projectName]);

  useEffect(() => {
    runningSessionsRef.current = runningSessions;
  }, [runningSessions]);

  // 遥测性能指标
  const [metrics, setMetrics] = useState<TelemetryMetrics>({
    turns: 1,
    steps: 1,
    total_time: "1.2s",
    tool_time: "0.4s",
    tokens_per_sec: 42.5,
    cache_hit_rate: 0.85,
    prompt_tokens: 125000,
    completion_tokens: 3200,
    total_tokens: 128200
  });

  const wsRef = useRef<WebSocket | null>(null);
  const scrollEndRef = useRef<HTMLDivElement | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const sessionScrollMap = useRef<Record<string, number>>({});

  // 全局阻止默认拖拽行为，防止 Electron 误将拖入窗口边缘的文件作为网页打开
  useEffect(() => {
    const handleGlobalDragOver = (e: DragEvent) => {
      e.preventDefault();
    };
    const handleGlobalDrop = (e: DragEvent) => {
      e.preventDefault();
    };
    window.addEventListener("dragover", handleGlobalDragOver);
    window.addEventListener("drop", handleGlobalDrop);
    return () => {
      window.removeEventListener("dragover", handleGlobalDragOver);
      window.removeEventListener("drop", handleGlobalDrop);
    };
  }, []);

  // 1. 初始化加载所有工作区项目、有效模型列表与活跃会话 (若后端正在启动，持续轮询重试直至成功获取真实项目与历史)
  useEffect(() => {
    fetchModels();
    fetchWorkspaces();

    const timer = setInterval(() => {
      setProjects((currentProjects) => {
        if (!currentProjects || currentProjects.length === 0 || (currentProjects.length === 1 && currentProjects[0].session_count === 0)) {
          fetchModels();
          fetchWorkspaces();
        } else {
          clearInterval(timer);
        }
        return currentProjects;
      });
    }, 1200);

    return () => clearInterval(timer);
  }, []);

  const fetchModels = () => {
    fetch("http://127.0.0.1:8765/api/models")
      .then((res) => res.json())
      .then((data) => {
        const list = data.models || [];
        setAvailableModels(list);
        setCurrentModel(data.current_model || (list.length > 0 ? list[0] : ""));
        if (data.model_providers) {
          setModelProviders(data.model_providers);
        }
      })
      .catch(() => {});
  };

  const fetchWorkspaces = (targetProject?: string, targetSession?: string, shouldLoadSession: boolean = true) => {
    fetch("http://127.0.0.1:8765/api/workspaces")
      .then((res) => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then((data) => {
        const projs: ProjectInfo[] = data.projects || [];
        setProjects(projs);

        const currentProj = targetProject || data.name || (projs.length > 0 ? projs[0].name : "super-harnes");
        setProjectName(currentProj);

        const matchedProj = projs.find((p) => p.name === currentProj) || (projs.length > 0 ? projs[0] : undefined);
        const projSessions = matchedProj?.sessions || [];
        setSessions(projSessions);

        const sid = targetSession || (projSessions.length > 0 ? projSessions[0].session_id : "default");
        setActiveSessionId(sid);

        if (shouldLoadSession) {
          loadSessionTurns(sid, matchedProj ? matchedProj.name : currentProj);
        }
      })
      .catch(() => {});
  };

  // 读取指定项目和会话的历史轮次 (智能保护内存中的在途轮次，杜绝二次发消息覆盖)
  const loadSessionTurns = (sid: string, targetProj?: string) => {
    const proj = targetProj || projectName;
    const key = getSessionKey(proj, sid);

    fetch(`http://127.0.0.1:8765/api/sessions/turns?session_id=${encodeURIComponent(sid)}&project=${encodeURIComponent(proj)}`)
      .then((res) => {
        if (!res.ok) throw new Error("加载会话历史失败");
        return res.json();
      })
      .then((data) => {
        if (data.turns && data.turns.length > 0) {
          setHasStarted(true);
          setSessionTurnsMap((prev) => {
            const curList = prev[key] || [];
            // 若内存中已有轮次且多于磁盘数据，绝对不能回退覆盖抹除最新对话气泡
            if (curList.length > data.turns.length) {
              return prev;
            }
            // 深度合并轮次：若内存中已有完整的 assistant_response，避免被磁盘临时空数据覆盖
            const mergedTurns = data.turns.map((dTurn: TurnData, idx: number) => {
              const memoryTurn = curList[idx];
              if (memoryTurn && memoryTurn.turn_id === dTurn.turn_id) {
                return {
                  ...dTurn,
                  attachments: (dTurn.attachments && dTurn.attachments.length > 0) ? dTurn.attachments : (memoryTurn.attachments || []),
                  assistant_response: dTurn.assistant_response || memoryTurn.assistant_response || "",
                  thought: dTurn.thought || memoryTurn.thought || "",
                  steps: (dTurn.steps && dTurn.steps.length > 0) ? dTurn.steps : (memoryTurn.steps || [])
                };
              }
              return dTurn;
            });
            return { ...prev, [key]: mergedTurns };
          });
          setSessionActionsMap((prev) => ({
            ...prev,
            [key]: data.all_actions || []
          }));
          setTasks(data.tasks || []);

          // 智能提取有效提问与标题：优先保留现有良好命名或首个非空提问，杜绝丢失标题
          const validTurn = (data.turns || []).find((t: any) => t.user_prompt && t.user_prompt.trim());
          const firstPrompt = validTurn?.user_prompt;
          const goal = data.working_memory?.current_goal;

          const currentItem = sessions.find((s) => s.session_id === sid);
          const existingTitle = currentItem && currentItem.current_goal && currentItem.current_goal !== sid
            ? currentItem.current_goal
            : null;

          const title = existingTitle || goal || (firstPrompt ? (firstPrompt.length > 28 ? firstPrompt.slice(0, 28) + "..." : firstPrompt) : `会话 ${sid}`);
          setSessionTitle(title);

          const lastTurn = data.turns[data.turns.length - 1];
          if (lastTurn) {
            setSessionThoughtMap((prev) => ({
              ...prev,
              [key]: lastTurn.thought || lastTurn.assistant_response || ""
            }));
          }

          setMetrics((prev) => ({
            ...prev,
            turns: data.turns_count || data.turns.length,
            steps: (data.all_actions || []).length || 1
          }));

          // 会话初次进入时默认滚动到底部最新消息，随后用户在该会话中的滚动位置会被完整保留
          if (sessionScrollMap.current[key] === undefined && key === getSessionKey(projectNameRef.current, activeSessionIdRef.current)) {
            requestAnimationFrame(() => {
              if (chatContainerRef.current) {
                chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
                sessionScrollMap.current[key] = chatContainerRef.current.scrollHeight;
              }
            });
          } else if (sessionScrollMap.current[key] !== undefined && key === getSessionKey(projectNameRef.current, activeSessionIdRef.current)) {
            requestAnimationFrame(() => {
              if (chatContainerRef.current) {
                chatContainerRef.current.scrollTop = sessionScrollMap.current[key];
              }
            });
          }
        } else {
          // 磁盘无历史轮次：检查内存中是否已有新发起的在途轮次，有则保留
          setSessionTurnsMap((prev) => {
            const curList = prev[key] || [];
            if (curList.length > 0) return prev;
            return { ...prev, [key]: [] };
          });
          setSessionTurnsMap((prev) => {
            const curList = prev[key] || [];
            if (curList.length === 0 && key === getSessionKey(projectNameRef.current, activeSessionIdRef.current)) {
              const currentProjObj = projects.find((p) => p.name === proj);
              const sessionList = currentProjObj ? currentProjObj.sessions : sessions;
              const targetSessionMeta = sessionList?.find((s) => s.session_id === sid);
              if (!targetSessionMeta || targetSessionMeta.turn_count === 0) {
                setHasStarted(false);
              }
            }
            return prev;
          });
          setSessionTitle(sid === "default" ? "默认会话" : sid);
        }
      })
      .catch(() => {});
  };

  // 2. 建立长期持久的双工 WebSocket 实时监听 (挂载时仅初始化一次，绝不在切换会话/项目时重连打断)
  useEffect(() => {
    let ws: WebSocket | null = null;
    let isUnmounted = false;

    const connect = () => {
      try {
        ws = new WebSocket("ws://127.0.0.1:8765/ws");

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            const targetSid = payload.session_id || activeSessionIdRef.current;
            const targetProj = payload.project || projectNameRef.current;
            const targetKey = getSessionKey(targetProj, targetSid);

            if (payload.event === "connected") {
              fetchModels();
              fetchWorkspaces();
            } else if (payload.event === "approval_required") {
              setApprovalReq({
                ticket_id: payload.ticket_id,
                command: payload.command,
                reason: payload.reason
              });
            } else if (payload.event === "thought") {
              const thText = payload.thought || "";
              setSessionThoughtMap((prev) => ({
                ...prev,
                [targetKey]: thText
              }));
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                const curTurn = updated[lastIdx];
                const curSteps = curTurn.steps || [];
                const newStep: TrajectoryStep = {
                  id: `th_${Date.now()}_${Math.random()}`,
                  type: "assistant",
                  thought: thText,
                  timestamp: Date.now()
                };
                updated[lastIdx] = {
                  ...curTurn,
                  thought: thText,
                  steps: [...curSteps, newStep]
                };
                return { ...prev, [targetKey]: updated };
              });
            } else if (payload.event === "tool_start" || payload.event === "tool_call_start") {
              const newAction: ToolAction = {
                id: payload.id || payload.tool_call_id || `act_${Date.now()}`,
                tool: payload.tool || payload.tool_name,
                display: payload.display || payload.tool_display || payload.tool,
                desc: payload.desc || "",
                path: payload.path,
                args: payload.args,
                status: "running",
                timestamp: Date.now()
              };
              setSessionActionsMap((prev) => ({
                ...prev,
                [targetKey]: [...(prev[targetKey] || []), newAction]
              }));

              const toolStep: TrajectoryStep = {
                id: newAction.id,
                type: "tool",
                tool: newAction.tool,
                display: newAction.display,
                desc: newAction.desc,
                path: newAction.path,
                args: payload.args,
                status: "running",
                timestamp: Date.now()
              };
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                const curTurn = updated[lastIdx];
                const curSteps = curTurn.steps || [];
                updated[lastIdx] = {
                  ...curTurn,
                  actions: [...(curTurn.actions || []), newAction],
                  steps: [...curSteps, toolStep]
                };
                return { ...prev, [targetKey]: updated };
              });
            } else if (payload.event === "tool_end" || payload.event === "tool_call_finished") {
              const tcId = payload.id || payload.tool_call_id;
              setSessionActionsMap((prev) => ({
                ...prev,
                [targetKey]: (prev[targetKey] || []).map((act) =>
                  act.id === tcId
                    ? {
                        ...act,
                        status: payload.status === "error" ? "error" : "success",
                        output: payload.output,
                        elapsed: payload.elapsed
                      }
                    : act
                )
              }));
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                const curTurn = updated[lastIdx];
                const updatedSteps = (curTurn.steps || []).map((st) =>
                  st.id === tcId
                    ? {
                        ...st,
                        status: (payload.status === "error" ? "error" : "success") as any,
                        output: payload.output,
                        elapsed: payload.elapsed
                      }
                    : st
                );
                const updatedActions = (curTurn.actions || []).map((act) =>
                  act.id === tcId
                    ? {
                        ...act,
                        status: (payload.status === "error" ? "error" : "success") as any,
                        output: payload.output,
                        elapsed: payload.elapsed
                      }
                    : act
                );
                updated[lastIdx] = {
                  ...curTurn,
                  actions: updatedActions,
                  steps: updatedSteps
                };
                return { ...prev, [targetKey]: updated };
              });
            } else if (payload.event === "stream_chunk") {
              const delta = payload.delta || "";
              setSessionThoughtMap((prev) => ({
                ...prev,
                [targetKey]: (prev[targetKey] || "") + delta
              }));
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                const curResponse = updated[lastIdx].assistant_response || "";
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  thought: "",
                  assistant_response: curResponse + delta
                };
                return { ...prev, [targetKey]: updated };
              });

              if (targetKey === getSessionKey(projectNameRef.current, activeSessionIdRef.current)) {
                scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
              }
            } else if (payload.event === "assistant_response") {
              // 精准释放目标会话的运行态
              setRunningSessions((prev) => ({ ...prev, [targetKey]: false }));

              if (payload.content && payload.content.includes("【会话已清空】")) {
                setSessionTurnsMap((prev) => ({ ...prev, [targetKey]: [] }));
                setSessionActionsMap((prev) => ({ ...prev, [targetKey]: [] }));
                setSessionThoughtMap((prev) => ({ ...prev, [targetKey]: "" }));
                if (targetKey === getSessionKey(projectNameRef.current, activeSessionIdRef.current)) {
                  setHasStarted(false);
                }
                return;
              }

              setSessionThoughtMap((prev) => ({ ...prev, [targetKey]: payload.content }));
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  assistant_response: payload.content,
                  elapsed: payload.elapsed !== undefined ? payload.elapsed : updated[lastIdx].elapsed
                };
                return { ...prev, [targetKey]: updated };
              });

              // 仅静默同步刷新侧边栏工作区会话元数据（如最新轮次与时间），绝不重新拉取磁盘覆盖内存中在途消息
              fetchWorkspaces(projectNameRef.current, activeSessionIdRef.current, false);
            } else if (payload.event === "error") {
              setRunningSessions((prev) => ({ ...prev, [targetKey]: false }));
              const errorMsg = `❌ 模型调用异常: ${payload.message || "请求失败"}\n\n💡 检查建议: 请前往右下角「+ 添加模型」或「系统设置 -> 模型」检查当前模型配置、API 密钥与网络连接是否有效。`;
              setSessionTurnsMap((prev) => {
                const list = prev[targetKey] || [];
                if (list.length === 0) return prev;
                const lastIdx = list.length - 1;
                const updated = [...list];
                if (!updated[lastIdx].assistant_response) {
                  updated[lastIdx] = {
                    ...updated[lastIdx],
                    assistant_response: errorMsg
                  };
                }
                return { ...prev, [targetKey]: updated };
              });
            } else if (payload.event === "metrics") {
              setMetrics({
                turns: payload.turns,
                steps: payload.steps,
                total_time: payload.total_time,
                tool_time: payload.tool_time,
                tokens_per_sec: payload.tokens_per_sec,
                cache_hit_rate: payload.cache_hit_rate,
                prompt_tokens: payload.prompt_tokens,
                completion_tokens: payload.completion_tokens,
                total_tokens: payload.total_tokens
              });
            }
          } catch (e) {}
        };

        ws.onopen = () => {
          setIsWsConnected(true);
        };

        ws.onclose = () => {
          setIsWsConnected(false);
          if (!isUnmounted) {
            setTimeout(connect, 2000);
          }
        };

        wsRef.current = ws;
      } catch (e) {}
    };

    connect();

    return () => {
      isUnmounted = true;
      ws?.close();
    };
  }, []);

  const handleScrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({ top: chatContainerRef.current.scrollHeight, behavior: "smooth" });
      const currentKey = getSessionKey(projectNameRef.current, activeSessionIdRef.current);
      sessionScrollMap.current[currentKey] = chatContainerRef.current.scrollHeight;
    }
  };

  // 视口滚动监听：实时记录当前会话停留的滚动位置
  const handleViewportScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const top = e.currentTarget.scrollTop;
    const currentKey = getSessionKey(projectNameRef.current, activeSessionIdRef.current);
    sessionScrollMap.current[currentKey] = top;
  };

  // 切换会话时，精准恢复上次停留的滚动位置，杜绝卡顿与跳动刷新
  useLayoutEffect(() => {
    if (!chatContainerRef.current) return;
    const key = getSessionKey(projectName, activeSessionId);
    const savedScroll = sessionScrollMap.current[key];
    if (savedScroll !== undefined) {
      chatContainerRef.current.scrollTop = savedScroll;
    }
  }, [activeSessionId, projectName]);

  // 在新增会话功能页面切换工作区：绝不跳转到旧对话，保持新建会话态，更新目标工作区
  const handleSelectProjectInEmptyState = (pname: string) => {
    setProjectName(pname);
    const newSid = `session_${Date.now()}`;
    setActiveSessionId(newSid);
    setHasStarted(false);

    const newKey = getSessionKey(pname, newSid);
    setSessionTurnsMap((prev) => ({ ...prev, [newKey]: [] }));
    setSessionActionsMap((prev) => ({ ...prev, [newKey]: [] }));
    setSessionThoughtMap((prev) => ({ ...prev, [newKey]: "" }));
    setSessionTitle("新会话");

    fetch("http://127.0.0.1:8765/api/workspaces/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: pname })
    })
      .then(() => {
        // 仅刷新侧边栏工作区项目结构，shouldLoadSession 设为 false，确保绝不跳转到历史对话
        fetchWorkspaces(pname, newSid, false);
      })
      .catch(() => {});
  };

  // 发送 Prompt 消息 (多会话并发状态完全隔离，支持附件上传与感知)
  const handleSendPrompt = (
    text: string, 
    model: string, 
    permission: string, 
    attachments: AttachmentItem[] = []
  ) => {
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;

    const targetKey = getSessionKey(projectName, activeSessionId);
    const isFirstTurn = !hasStarted || (sessionTurnsMap[targetKey] || []).length === 0;

    // 若输入快捷清空命令，重置当前会话内存
    if (trimmed.toLowerCase() === "/clear" || trimmed.toLowerCase() === "/reset") {
      setSessionTurnsMap((prev) => ({ ...prev, [targetKey]: [] }));
      setSessionActionsMap((prev) => ({ ...prev, [targetKey]: [] }));
      setSessionThoughtMap((prev) => ({ ...prev, [targetKey]: "" }));
      setHasStarted(false);
    } else {
      setHasStarted(true);

      const titleCandidate = trimmed 
        ? text.slice(0, 24) 
        : (attachments[0] ? `附件: ${attachments[0].name}` : "新会话");

      // 若是在新建会话页面首次发送消息，立刻在该工作区侧边栏中渲染出该新建聊天框
      if (isFirstTurn) {
        setProjects((prevProjs) =>
          prevProjs.map((p) => {
            if (p.name === projectName) {
              const exists = (p.sessions || []).some((s) => s.session_id === activeSessionId);
              if (!exists) {
                const newSessionItem: SessionInfo = {
                  session_id: activeSessionId,
                  is_active: true,
                  turn_count: 1,
                  current_goal: titleCandidate,
                  time_ago: "刚刚",
                  is_pinned: false
                };
                return {
                  ...p,
                  session_count: (p.sessions || []).length + 1,
                  sessions: [newSessionItem, ...(p.sessions || [])]
                };
              }
            }
            return p;
          })
        );

        fetch("http://127.0.0.1:8765/api/sessions/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project: projectName, session_id: activeSessionId })
        }).catch(() => {});
      }

      // 乐观添加新的一轮至专属隔离会话字典 (包含附件)
      const curList = sessionTurnsMap[targetKey] || [];
      const tempTurn: TurnData = {
        turn_id: curList.length + 1,
        user_prompt: text,
        attachments: attachments,
        thought: "正在深度思考与执行下一步排查...",
        assistant_response: "",
        actions: [],
        steps: [],
        timestamp: Date.now() / 1000
      };
      setSessionTurnsMap((prev) => ({
        ...prev,
        [targetKey]: [...(prev[targetKey] || []), tempTurn]
      }));
      setSessionThoughtMap((prev) => ({ ...prev, [targetKey]: "正在深度思考与执行下一步排查..." }));

      // 发送消息后模拟鼠标平滑下滑至最新消息处 (对标需求 1)
      setTimeout(() => {
        if (chatContainerRef.current) {
          chatContainerRef.current.scrollTo({
            top: chatContainerRef.current.scrollHeight,
            behavior: "smooth"
          });
        }
        scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 50);
    }

    // 仅锁定当前复合键对应的会话
    setRunningSessions((prev) => ({ ...prev, [targetKey]: true }));
    const titleCandidate = trimmed 
      ? text.slice(0, 24) 
      : (attachments[0] ? `附件: ${attachments[0].name}` : "新会话");
    setSessionTitle(titleCandidate);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "prompt",
          prompt: text,
          attachments: attachments,
          model: model,
          permission_mode: permission.toLowerCase().includes("ask") ? "ask" : "auto",
          session_id: activeSessionId,
          project_name: projectName
        })
      );
    } else {
      setTimeout(() => {
        setRunningSessions((prev) => ({ ...prev, [targetKey]: false }));
        setSessionThoughtMap((prev) => ({
          ...prev,
          [targetKey]: "⚠️ 后端服务正在建立连接，请稍候 1~2 秒后重试发送..."
        }));
      }, 500);
    }
  };

  // 暂停当前会话的思考与执行 (对标需求 2)
  const handlePause = () => {
    const targetKey = getSessionKey(projectNameRef.current, activeSessionIdRef.current);
    setRunningSessions((prev) => ({ ...prev, [targetKey]: false }));

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "abort",
          session_id: activeSessionIdRef.current,
          project_name: projectNameRef.current
        })
      );
    }

    setSessionTurnsMap((prev) => {
      const list = prev[targetKey] || [];
      if (list.length === 0) return prev;
      const lastIdx = list.length - 1;
      const updated = [...list];
      const cur = updated[lastIdx];
      if (!cur.assistant_response) {
        updated[lastIdx] = {
          ...cur,
          assistant_response: "【用户已手动暂停】已终止当前思考与工具调用。"
        };
      }
      return { ...prev, [targetKey]: updated };
    });
  };

  // 用户气泡就地编辑并重发此轮 (对标需求 2)
  const handleResendTurn = (turnId: number, newPrompt: string) => {
    const targetKey = getSessionKey(projectName, activeSessionId);
    if (runningSessions[targetKey]) {
      handlePause();
    }

    setSessionTurnsMap((prev) => {
      const list = prev[targetKey] || [];
      const turnIdx = list.findIndex((t) => t.turn_id === turnId);
      if (turnIdx === -1) return prev;
      const keptTurns = list.slice(0, turnIdx);
      return { ...prev, [targetKey]: keptTurns };
    });

    setTimeout(() => {
      handleSendPrompt(newPrompt, currentModel, modeName);
    }, 60);
  };

  // 切换工作区/项目 (侧边栏触发)
  const handleSelectProject = (pname: string) => {
    setProjectName(pname);
    fetch("http://127.0.0.1:8765/api/workspaces/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: pname })
    })
      .then(() => {
        // 若当前处于新建会话未开始态，切换侧边栏项目也保持新建会话态
        fetchWorkspaces(pname, undefined, hasStarted);
      })
      .catch(() => {});
  };

  // 选择会话 (保留并优先恢复内存中在途消息，并记住上一会话的滚动停留位置)
  const handleSelectSession = (sid: string, projName?: string) => {
    if (chatContainerRef.current) {
      const currentKey = getSessionKey(projectName, activeSessionId);
      sessionScrollMap.current[currentKey] = chatContainerRef.current.scrollTop;
    }
    const targetProj = projName || projectName;
    if (targetProj !== projectName) {
      setProjectName(targetProj);
    }
    setActiveSessionId(sid);

    const targetKey = getSessionKey(targetProj, sid);
    const cachedTurns = sessionTurnsMap[targetKey];
    if (cachedTurns && cachedTurns.length > 0) {
      setHasStarted(true);
    } else {
      // 检查当前会话是否为既有历史会话 (避免在数据返回前闪烁新建会话/空态视图)
      const currentProjObj = projects.find((p) => p.name === targetProj);
      const sessionList = currentProjObj ? currentProjObj.sessions : sessions;
      const targetSessionMeta = sessionList?.find((s) => s.session_id === sid);
      if (targetSessionMeta && (targetSessionMeta.turn_count > 0 || targetSessionMeta.current_goal)) {
        setHasStarted(true);
      } else {
        // 点击侧边栏已有会话时，绝不提前置为 false，先保持为 true 显示过渡态，彻底杜绝闪烁新建会话页面
        setHasStarted(true);
      }
    }

    loadSessionTurns(sid, targetProj);
  };

  // 新建会话 (注册全新隔离复合键)
  const handleNewSession = () => {
    fetch("http://127.0.0.1:8765/api/sessions/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: projectName })
    })
      .then((res) => res.json())
      .then((data) => {
        const newSid = data.session_id || `session_${Date.now()}`;
        const newKey = getSessionKey(projectName, newSid);
        setActiveSessionId(newSid);
        setHasStarted(false);
        setSessionTurnsMap((prev) => ({ ...prev, [newKey]: [] }));
        setSessionActionsMap((prev) => ({ ...prev, [newKey]: [] }));
        setSessionThoughtMap((prev) => ({ ...prev, [newKey]: "" }));
        setSessionTitle("新会话");
        fetchWorkspaces(projectName, newSid);
      })
      .catch(() => {
        setHasStarted(false);
      });
  };

  // 选择磁盘项目并添加新工作区
  const handleAddWorkspace = async () => {
    let selectedDir: string | null = null;
    const electronAPI = (window as any).electronAPI;

    if (electronAPI?.selectDirectory) {
      try {
        selectedDir = await electronAPI.selectDirectory();
      } catch (e) {}
    } else {
      selectedDir = window.prompt("请输入本地项目文件夹路径:");
    }

    if (!selectedDir) return;

    fetch("http://127.0.0.1:8765/api/workspaces/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: selectedDir })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.name) {
          handleSelectProjectInEmptyState(data.name);
        }
      })
      .catch(() => {});
  };

  // 切换大模型
  const handleSelectModel = (m: string) => {
    setCurrentModel(m);
    fetch("http://127.0.0.1:8765/api/models/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: m })
    }).catch(() => {});
  };

  // 自定义提供方与模型更新回调
  const handleProvidersUpdated = (_providers: any[], activeModels: string[]) => {
    if (activeModels && activeModels.length > 0) {
      setAvailableModels(activeModels);
      if (!activeModels.includes(currentModel)) {
        setCurrentModel(activeModels[0]);
      }
    }
    fetchModels();
  };

  // 1. 编辑工作区 (更改名称及磁盘目录)
  const handleEditProject = (oldName: string, newName: string, path?: string) => {
    fetch("http://127.0.0.1:8765/api/workspaces/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_name: oldName, new_name: newName, path })
    })
      .then((res) => res.json())
      .then(() => {
        fetchWorkspaces(newName);
      })
      .catch(() => {});
  };

  // 2. 置顶 / 取消置顶工作区
  const handlePinProject = (name: string, pinned: boolean) => {
    fetch("http://127.0.0.1:8765/api/workspaces/pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, pinned })
    })
      .then(() => {
        fetchWorkspaces(projectName);
      })
      .catch(() => {});
  };

  // 3. 删除工作区 (自定义圆角确认弹窗)
  const handleDeleteProject = (name: string) => {
    setConfirmDialog({
      isOpen: true,
      title: "删除工作区",
      message: `确定要删除工作区 “${name}” 的全部记录吗？删除后此项目的历史记录将从本地清除。`,
      onConfirm: () => {
        setConfirmDialog(null);
        fetch("http://127.0.0.1:8765/api/workspaces/delete", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name })
        })
          .then(() => {
            if (name === projectName) {
              const fallbackProj = projects.find((p) => p.name !== name)?.name || "super-harnes";
              fetchWorkspaces(fallbackProj);
            } else {
              fetchWorkspaces(projectName);
            }
          })
          .catch(() => {});
      }
    });
  };

  // 4. 重命名会话
  const handleRenameSession = (project: string, sid: string, newTitle: string) => {
    fetch("http://127.0.0.1:8765/api/sessions/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, session_id: sid, new_title: newTitle })
    })
      .then(() => {
        fetchWorkspaces(project, sid);
      })
      .catch(() => {});
  };

  // 5. 置顶 / 取消置顶会话
  const handlePinSession = (project: string, sid: string, pinned: boolean) => {
    fetch("http://127.0.0.1:8765/api/sessions/pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, session_id: sid, pinned })
    })
      .then(() => {
        fetchWorkspaces(project, activeSessionId);
      })
      .catch(() => {});
  };

  // 6. 删除会话 (自定义圆角确认弹窗)
  const handleDeleteSession = (project: string, sid: string) => {
    setConfirmDialog({
      isOpen: true,
      title: "删除会话",
      message: "确定要删除此会话记录吗？删除后将无法恢复该对话内容。",
      onConfirm: () => {
        setConfirmDialog(null);
        fetch("http://127.0.0.1:8765/api/sessions/delete", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project, session_id: sid })
        })
          .then(() => {
            if (sid === activeSessionId) {
              handleNewSession();
            } else {
              fetchWorkspaces(project);
            }
          })
          .catch(() => {});
      }
    });
  };

  return (
    <div className={`flex h-screen w-screen overflow-hidden font-sans select-text transition-colors duration-150 ${
      theme === "dark" ? "bg-[#0f1117] text-gray-100 dark" : "bg-white text-gray-900"
    }`}>
      {/* 1. 左侧工作区导航栏 (展示 4 个项目的全部聊天历史，透明图形 Logo) */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        projectName={projectName}
        projects={projects}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onSelectProject={handleSelectProject}
        onNewSession={handleNewSession}
        onAddWorkspace={handleAddWorkspace}
        onOpenSettings={() => setShowSettings(true)}
        onOpenPlugins={() => setShowPlugins(true)}
        onEditProject={handleEditProject}
        onPinProject={handlePinProject}
        onDeleteProject={handleDeleteProject}
        onRenameSession={handleRenameSession}
        onPinSession={handlePinSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* 2. 主操作区 */}
      <div className="flex-1 h-full flex flex-col bg-white dark:bg-[#0f1117] overflow-hidden relative transition-colors">
        {!isWsConnected && (
          <div className="w-full bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 flex items-center justify-center gap-2 text-xs text-amber-600 dark:text-amber-400 select-none animate-pulse z-50">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
            <span>正在连接后端服务 (127.0.0.1:8765)... 若刚启动请稍候</span>
          </div>
        )}
        {/* 顶部标题栏 (展示当前工程与对话/轨迹切换，未开始时显示窗口操作按钮) */}
        {hasStarted ? (
          <Header
            sessionTitle={sessionTitle}
            projectName={projectName}
            modeName={modeName}
            activeTab={activeTab}
            onTabChange={(tab) => setActiveTab(tab)}
            onExportLog={() => {}}
          />
        ) : (
          <div className="h-16 flex items-center justify-end px-5 titlebar-drag-region select-none shrink-0 bg-transparent transition-colors">
            <div className="titlebar-no-drag">
              <WindowControls />
            </div>
          </div>
        )}

        {/* 主视口内容区 */}
        <div
          ref={chatContainerRef}
          onScroll={handleViewportScroll}
          className="flex-1 overflow-y-auto px-6 py-4 flex flex-col"
        >
          {!hasStarted ? (
            /* 空态居中视图：支持选择工作区、添加磁盘项目、+ 号快捷指令与配置模型 */
            <EmptyState
              projectName={projectName}
              sessionId={activeSessionId}
              projects={projects}
              modeName={modeName}
              onSend={handleSendPrompt}
              isLoading={isCurrentSessionLoading}
              models={availableModels}
              selectedModel={currentModel}
              modelProviders={modelProviders}
              onSelectModel={handleSelectModel}
              onOpenModelSettings={() => setShowSettings(true)}
              onSelectProject={handleSelectProjectInEmptyState}
              onAddWorkspace={handleAddWorkspace}
              onPause={handlePause}
            />
          ) : (
            /* 会话执行态：支持“对话”与“轨迹”双模自由切换，流式逐字输出 */
            <div className="max-w-4xl w-full mx-auto flex-1 flex flex-col">

              {activeTab === "chat" ? (
                /* 对话流视图：展示完整历史问答轮次、实时流式思考与折叠步骤 (对标图四) */
                <div className="space-y-2 flex-1">
                  {turns.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500 py-24 select-none">
                      <div className="flex items-center gap-2.5 text-xs">
                        <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                        <span>正在加载历史会话...</span>
                      </div>
                    </div>
                  ) : (
                    turns.map((turn, idx) => (
                      <ChatMessage
                        key={turn.turn_id}
                        turn={turn}
                        isLoading={isCurrentSessionLoading && idx === turns.length - 1}
                        isLatestTurn={idx === turns.length - 1}
                        onOpenFile={(p) => setSelectedFile(p)}
                        onEditPrompt={(txt) => setDraftPrompt(txt)}
                        onResendTurn={handleResendTurn}
                        onOpenSettings={() => setShowSettings(true)}
                      />
                    ))
                  )}
                  {isCurrentSessionLoading && turns.length === 0 && (
                    <div className="flex items-center gap-3 p-3 bg-blue-50/50 border border-blue-100 rounded-2xl text-xs text-blue-700 animate-pulse">
                      <img src={LOGO_DATA_URI} alt="super logo" className="w-5 h-5 object-contain shrink-0" />
                      <span>super 智能体正在流式思考与组织回复...</span>
                    </div>
                  )}
                </div>
              ) : (
                /* 轨迹流视图：100% 对标图一标准，连贯时间线，醒目 TOOL / ASSISTANT 徽标与请求出参卡片 */
                <div className="flex-1 flex flex-col space-y-4">
                  <TrajectoryTimeline
                    turns={turns}
                    rawActions={actions}
                    thoughtText={thoughtText}
                    onOpenFile={(p) => setSelectedFile(p)}
                  />
                  <TaskDrawer tasks={tasks} />
                </div>
              )}

              <div ref={scrollEndRef} className="h-4" />
            </div>
          )}
        </div>

        {/* 底部吸附输入栏 (带 '+' 快捷指令菜单、📎 附件上传、AUTO 模式、点击空白关闭下拉) */}
        {hasStarted && (
          <BottomInput
            onSend={handleSendPrompt}
            isLoading={isCurrentSessionLoading}
            metrics={metrics}
            onScrollToBottom={handleScrollToBottom}
            models={availableModels}
            selectedModel={currentModel}
            modelProviders={modelProviders}
            onSelectModel={handleSelectModel}
            onOpenModelSettings={() => setShowSettings(true)}
            draftText={draftPrompt}
            onDraftConsumed={() => setDraftPrompt("")}
            onPause={handlePause}
            projectName={projectName}
            sessionId={activeSessionId}
          />
        )}
      </div>

      {/* 3. 模态框与抽屉组件 */}
      <FileViewerModal filePath={selectedFile} onClose={() => setSelectedFile(null)} />
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        currentModel={currentModel}
        onSaveModel={handleSelectModel}
        onProvidersUpdated={handleProvidersUpdated}
        theme={theme}
        onSelectTheme={(t) => setTheme(t)}
        fontSizeLevel={fontSizeLevel}
        onSelectFontSize={(lvl) => setFontSizeLevel(lvl)}
      />
      <PluginsModal isOpen={showPlugins} onClose={() => setShowPlugins(false)} />
      <ApprovalModal
        request={approvalReq}
        onApprove={() => setApprovalReq(null)}
        onReject={() => setApprovalReq(null)}
      />
      <ConfirmModal
        isOpen={Boolean(confirmDialog?.isOpen)}
        title={confirmDialog?.title || "操作确认"}
        message={confirmDialog?.message || ""}
        confirmText="确定删除"
        danger={true}
        onConfirm={() => {
          if (confirmDialog?.onConfirm) confirmDialog.onConfirm();
        }}
        onCancel={() => setConfirmDialog(null)}
      />
    </div>
  );
};
