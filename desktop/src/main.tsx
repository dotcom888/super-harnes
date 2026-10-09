import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen w-screen bg-[#f8fafc] text-gray-800 p-8 select-none">
          <div className="max-w-md w-full bg-white rounded-2xl shadow-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-base font-bold text-red-600">应用渲染出现异常</h2>
            <p className="text-xs text-gray-600 font-mono bg-gray-50 p-2.5 rounded-lg break-all">
              {this.state.error?.message || "未知渲染错误"}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-medium cursor-pointer transition"
            >
              重新加载应用
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
