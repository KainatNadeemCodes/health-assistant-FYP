/**
 * FILE: src/components/ErrorBoundary.tsx
 * PURPOSE: Global React Error Boundary to catch render errors and prevent white-screen crashes.
 * VERSION: 1.0  |  GROUP: F25PROJECT664B0
 */

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled rendering error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  public handleGoHome = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = "/";
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-6">
          <div className="max-w-lg w-full rounded-2xl border border-destructive/20 bg-card p-8 shadow-xl text-center space-y-6">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertTriangle className="h-8 w-8" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                Something Went Wrong
              </h2>
              <p className="text-sm text-muted-foreground">
                The application encountered an unexpected interface error. Your session
                and data are preserved. You can retry the action or return to the home screen.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button
                variant="outline"
                onClick={this.handleReset}
                className="w-full sm:w-auto flex items-center gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Try Again
              </Button>
              <Button
                variant="default"
                onClick={this.handleGoHome}
                className="w-full sm:w-auto flex items-center gap-2"
              >
                <Home className="h-4 w-4" />
                Return to Home
              </Button>
            </div>

            {process.env.NODE_ENV !== "production" && this.state.error && (
              <details className="mt-4 text-left text-xs bg-muted/60 p-3 rounded-lg border border-border overflow-auto max-h-40">
                <summary className="cursor-pointer font-medium text-destructive mb-1">
                  Developer Error Details
                </summary>
                <p className="font-mono text-destructive">{this.state.error.toString()}</p>
                {this.state.errorInfo && (
                  <pre className="font-mono text-[10px] text-muted-foreground mt-2 whitespace-pre-wrap">
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
