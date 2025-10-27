import mitt, { Emitter } from "mitt";

export type SessionEventMap = {
  open: WebSocket;
  close: CloseEvent | Event;
  error: Event;
  message: MessageEvent;
  reconnecting: number;
  reconnected: number;
  offline: void;
  online: void;
  summary: SessionSummaryPayload;
};

export interface SessionSummaryPayload {
  transcript: string[];
  vocabularyLearned: string[];
  xpEarned: number;
  feedback: string;
}

export interface WebSocketClientOptions {
  url: string;
  token?: string;
  maxRetries?: number;
  retryDelayMs?: number;
  retryMultiplier?: number;
  offlineQueueLimit?: number;
}

const DEFAULT_OPTIONS: Required<Omit<WebSocketClientOptions, "url" | "token">> = {
  maxRetries: 5,
  retryDelayMs: 1000,
  retryMultiplier: 1.8,
  offlineQueueLimit: 50,
};

export class WebSocketClient {
  private socket?: WebSocket;
  private options: Required<WebSocketClientOptions>;
  private emitter: Emitter<SessionEventMap> = mitt<SessionEventMap>();
  private reconnectAttempts = 0;
  private manualClose = false;
  private offlineQueue: string[] = [];

  constructor(options: WebSocketClientOptions) {
    if (!options.url) {
      throw new Error("WebSocketClient requires a URL");
    }

    this.options = {
      ...DEFAULT_OPTIONS,
      ...options,
      maxRetries: options.maxRetries ?? DEFAULT_OPTIONS.maxRetries,
      retryDelayMs: options.retryDelayMs ?? DEFAULT_OPTIONS.retryDelayMs,
      retryMultiplier: options.retryMultiplier ?? DEFAULT_OPTIONS.retryMultiplier,
      offlineQueueLimit: options.offlineQueueLimit ?? DEFAULT_OPTIONS.offlineQueueLimit,
    } as Required<WebSocketClientOptions>;

    if (typeof window !== "undefined") {
      window.addEventListener("online", this.handleOnline);
      window.addEventListener("offline", this.handleOffline);
    }
  }

  connect(): void {
    const { url, token } = this.options;
    const socketUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;

    this.manualClose = false;
    this.socket = new WebSocket(socketUrl);

    this.socket.addEventListener("open", this.onOpen);
    this.socket.addEventListener("close", this.onClose);
    this.socket.addEventListener("error", this.onError);
    this.socket.addEventListener("message", this.onMessage);
  }

  disconnect(): void {
    this.manualClose = true;
    if (this.socket) {
      this.socket.removeEventListener("open", this.onOpen);
      this.socket.removeEventListener("close", this.onClose);
      this.socket.removeEventListener("error", this.onError);
      this.socket.removeEventListener("message", this.onMessage);
      this.socket.close();
      this.socket = undefined;
    }
    if (typeof window !== "undefined") {
      window.removeEventListener("online", this.handleOnline);
      window.removeEventListener("offline", this.handleOffline);
    }
  }

  send(data: unknown): void {
    const payload = JSON.stringify(data);

    if (typeof navigator !== "undefined" && !navigator.onLine) {
      this.enqueueOffline(payload);
      return;
    }

    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(payload);
    } else {
      this.enqueueOffline(payload);
    }
  }

  on<Type extends keyof SessionEventMap>(event: Type, handler: (value: SessionEventMap[Type]) => void): void {
    this.emitter.on(event, handler);
  }

  off<Type extends keyof SessionEventMap>(event: Type, handler: (value: SessionEventMap[Type]) => void): void {
    this.emitter.off(event, handler);
  }

  private onOpen = (event: Event) => {
    this.reconnectAttempts = 0;
    this.emitter.emit("open", event.currentTarget as WebSocket);
    this.flushOfflineQueue();
  };

  private onClose = (event: CloseEvent | Event) => {
    this.emitter.emit("close", event);
    if (this.manualClose) {
      return;
    }

    if (this.reconnectAttempts < this.options.maxRetries) {
      this.reconnectAttempts += 1;
      this.emitter.emit("reconnecting", this.reconnectAttempts);
      const delay = this.options.retryDelayMs * Math.pow(this.options.retryMultiplier, this.reconnectAttempts - 1);
      setTimeout(() => {
        this.emitter.emit("reconnected", this.reconnectAttempts);
        this.connect();
      }, delay);
    } else {
      this.emitter.emit("offline");
    }
  };

  private onError = (event: Event) => {
    this.emitter.emit("error", event);
  };

  private onMessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      if (data?.type === "session_summary") {
        this.emitter.emit("summary", data.payload as SessionSummaryPayload);
      } else {
        this.emitter.emit("message", event);
      }
    } catch (error) {
      this.emitter.emit("error", error as Event);
    }
  };

  private handleOnline = () => {
    this.emitter.emit("online");
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
    }
  };

  private handleOffline = () => {
    this.emitter.emit("offline");
  };

  private enqueueOffline(payload: string) {
    if (this.offlineQueue.length >= this.options.offlineQueueLimit) {
      this.offlineQueue.shift();
    }
    this.offlineQueue.push(payload);
  }

  private flushOfflineQueue() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    while (this.offlineQueue.length > 0) {
      const payload = this.offlineQueue.shift();
      if (payload) {
        this.socket.send(payload);
      }
    }
  }
}
