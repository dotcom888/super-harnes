import { AttachmentItem } from "../types";

export interface DraftData {
  text: string;
  attachments: AttachmentItem[];
}

// 从剪贴板读取文件或截图图片 (优先走 Electron 原生 IPC 读取 Windows 文件/图片，回退 Web Clipboard API)
export async function readMediaFromClipboard(): Promise<File[] | null> {
  try {
    if ((window as any).electronAPI?.readClipboardMedia) {
      const media = await (window as any).electronAPI.readClipboardMedia();
      const filesToUpload: File[] = [];

      if (media.files && media.files.length > 0) {
        for (const f of media.files) {
          const byteCharacters = atob(f.dataBase64);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          filesToUpload.push(new File([byteArray], f.name, { type: "application/octet-stream" }));
        }
        return filesToUpload;
      }

      if (media.image) {
        const byteCharacters = atob(media.image.dataBase64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        filesToUpload.push(new File([byteArray], media.image.name, { type: "image/png" }));
        return filesToUpload;
      }
    }
  } catch (err) {
    console.warn("Electron clipboard media read failed, falling back to Web API:", err);
  }

  // 浏览器环境兜底：尝试 navigator.clipboard.read()
  try {
    if (navigator.clipboard && navigator.clipboard.read) {
      const items = await navigator.clipboard.read();
      const files: File[] = [];
      for (const item of items) {
        for (const type of item.types) {
          if (type.startsWith("image/")) {
            const blob = await item.getType(type);
            const ext = type.split("/")[1] || "png";
            files.push(new File([blob], `screenshot_${Date.now()}.${ext}`, { type }));
          }
        }
      }
      if (files.length > 0) return files;
    }
  } catch {}

  return null;
}

// 提取剪贴板事件中的文件/图片
export function extractFilesFromClipboardEvent(e: React.ClipboardEvent): File[] {
  const clipboardData = e.clipboardData;
  if (!clipboardData) return [];

  const filesToUpload: File[] = [];

  if (clipboardData.files && clipboardData.files.length > 0) {
    for (let i = 0; i < clipboardData.files.length; i++) {
      const file = clipboardData.files[i];
      if (file && file.size > 0) {
        filesToUpload.push(file);
      }
    }
  }

  if (filesToUpload.length === 0 && clipboardData.items && clipboardData.items.length > 0) {
    for (let i = 0; i < clipboardData.items.length; i++) {
      const item = clipboardData.items[i];
      if (item.kind === "file") {
        const blob = item.getAsFile();
        if (blob) {
          let filename = blob.name;
          if (!filename || filename === "image.png") {
            const ext = (blob.type && blob.type.split("/")[1]) || "png";
            filename = `screenshot_${Date.now()}.${ext}`;
          }
          filesToUpload.push(new File([blob], filename, { type: blob.type || "image/png" }));
        }
      }
    }
  }

  return filesToUpload;
}

// 草稿持久保护：双保险存储 (sessionStorage 保证无感即时恢复，localStorage 保证窗口重载不丢)
export function saveDraft(key: string, text: string, attachments: AttachmentItem[]) {
  try {
    const payload = JSON.stringify({ text, attachments, ts: Date.now() });
    sessionStorage.setItem(`super_draft_${key}`, payload);
    localStorage.setItem(`super_draft_${key}`, payload);
  } catch {}
}

export function loadDraft(key: string): DraftData {
  try {
    const raw = sessionStorage.getItem(`super_draft_${key}`) || localStorage.getItem(`super_draft_${key}`);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        text: typeof parsed.text === "string" ? parsed.text : "",
        attachments: Array.isArray(parsed.attachments) ? parsed.attachments : []
      };
    }
  } catch {}
  return { text: "", attachments: [] };
}

export function clearDraft(key: string) {
  try {
    sessionStorage.removeItem(`super_draft_${key}`);
    localStorage.removeItem(`super_draft_${key}`);
  } catch {}
}
