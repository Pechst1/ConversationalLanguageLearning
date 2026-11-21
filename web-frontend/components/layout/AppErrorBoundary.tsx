/**
 * S4 stage 2 — a crash while a page is drawn no longer shows Next's English
 * default. The boundary reports it through the same silent reporter as the
 * window listeners (`_app.tsx`) and prints the event id that report carries.
 * A new route (`resetKey`) clears it.
 */
import React from 'react';

import { ErrorScreen } from './ErrorScreen';

type Props = {
  children: React.ReactNode;
  /** Sends the report and returns its event id. */
  report: (message: string, stack?: string) => string;
  resetKey?: string;
};

type State = { failed: boolean; eventId: string | null; resetKey?: string };

export default class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { failed: false, eventId: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.resetKey) return { failed: false, eventId: null, resetKey: props.resetKey };
    return null;
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    const eventId = this.props.report(message, [stack, info?.componentStack].filter(Boolean).join('\n'));
    this.setState({ eventId });
  }

  render() {
    if (this.state.failed) return <ErrorScreen kind="crashed" eventId={this.state.eventId} reload />;
    return this.props.children;
  }
}
