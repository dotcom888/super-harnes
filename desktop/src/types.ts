export interface AttachmentItem {
  id: string;
  name: string;
  size: number;
  type: 'text' | 'word' | 'pdf' | 'excel' | 'image' | 'other' | string;
  path: string;
  url?: string;
  dataUrl?: string;
}

export interface ToolAction {
  id: string;
  tool: string;
  display: 'Pwsh' | 'Read' | 'Edit' | 'Grep' | 'Glob' | string;
  desc: string;
  path?: string;
  args?: Record<string, any>;
  status?: 'running' | 'success' | 'error';
  output?: string;
  elapsed?: number;
  timestamp: number;
}

export interface TaskItem {
  id: string;
  title: string;
  completed: boolean;
}

export interface TrajectoryStep {
  id: string;
  type: 'tool' | 'assistant' | 'user';
  tool?: string;
  display?: string;
  desc?: string;
  path?: string;
  args?: Record<string, any> | string;
  output?: string;
  status?: 'running' | 'success' | 'error';
  elapsed?: number;
  thought?: string;
  content?: string;
  timestamp?: number;
}

export interface TurnData {
  turn_id: number;
  user_prompt: string;
  attachments?: AttachmentItem[];
  thought?: string;
  assistant_response?: string;
  actions: ToolAction[];
  steps?: TrajectoryStep[];
  timestamp?: number;
  elapsed?: number;
}

export interface MessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  toolActions?: ToolAction[];
}

export interface SessionInfo {
  session_id: string;
  is_active: boolean;
  turn_count: number;
  modified_files_count?: number;
  current_goal?: string;
  has_disk_file?: boolean;
  time_ago?: string;
  is_pinned?: boolean;
}

export interface ProjectInfo {
  name: string;
  path?: string;
  session_count: number;
  sessions: SessionInfo[];
  is_pinned?: boolean;
}

export interface ModelProvider {
  id?: string;
  name: string;
  base_url: string;
  api_key_masked?: string;
  api_key?: string;
  models: string[];
  is_custom: boolean;
  protocol?: string;
  status: 'connected' | 'unconfigured';
}

export interface TelemetryMetrics {
  turns: number;
  steps: number;
  total_time: string;
  tool_time: string;
  tokens_per_sec: number;
  cache_hit_rate: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface SystemStatus {
  ready: boolean;
  project_name: string;
  workspace_path: string;
  active_session_id: string;
  model: string;
  permission_mode: string;
  turn_count: number;
  tools_count: number;
  mcp_clients_count: number;
}
export interface UserInputRequest {
  request_id: string;
  question: string;
  header?: string;
  options?: string[];
  allow_custom?: boolean;
  session_id?: string;
  project?: string;
}
