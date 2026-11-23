import { Shell } from "@/components/shell";
import { ThemeProvider } from "@/lib/theme";
import { Component, type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { HomePage } from "@/pages/home";
import { RegistryPage } from "@/pages/registry";
import { RunPage } from "@/pages/run";
import { RunsPage } from "@/pages/runs";
import { SettingsPage } from "@/pages/settings";

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <ErrorBoundary>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<HomePage />} />
              <Route path="runs" element={<RunsPage />} />
              <Route path="runs/:id" element={<RunPage />} />
              <Route path="registry" element={<RegistryPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </ErrorBoundary>
        <Toaster richColors position="top-right" />
      </BrowserRouter>
    </ThemeProvider>
  );
}

class ErrorBoundary extends Component<{ children: ReactNode }, { message: string | null }> {
  state = { message: null as string | null };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message };
  }

  render() {
    if (this.state.message) {
      return (
        <div className="grid min-h-screen place-items-center px-6">
          <div className="max-w-md">
            <h1 className="text-lg font-semibold">The console hit an error</h1>
            <p className="mt-2 text-sm text-zinc-500">{this.state.message}</p>
            <button className="mt-4 text-sm underline" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
