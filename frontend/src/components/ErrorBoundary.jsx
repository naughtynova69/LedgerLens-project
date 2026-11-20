import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error?.message || "An unexpected interface error occurred.",
    };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border border-gray-200 rounded-xl p-6 space-y-4 text-center">
            <div className="text-xs font-mono uppercase tracking-wider text-red-700 bg-red-50 border border-red-200 inline-block px-2.5 py-1 rounded-md">
              LedgerLens Recovery
            </div>
            <h1 className="text-base font-semibold text-[#111827]">
              Something went wrong rendering this view
            </h1>
            <p className="text-xs text-[#6B7280] break-words">
              {this.state.message}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-[#111827] hover:bg-gray-800 text-white text-xs font-medium transition-colors"
            >
              Reload LedgerLens
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
