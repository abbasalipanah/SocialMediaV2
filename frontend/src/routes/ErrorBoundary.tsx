import { Component, type ErrorInfo, type ReactNode } from "react";

import { ScreenState } from "../ui";

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) console.error(error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <ScreenState eyebrow="Application error" title="This view could not be opened">
          <p>Reload the application to retry with a clean route state.</p>
          <button className="primary-button" onClick={() => window.location.reload()} type="button">
            Reload
          </button>
        </ScreenState>
      );
    }
    return this.props.children;
  }
}
