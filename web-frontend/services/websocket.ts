import { useEffect, useRef, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import toast from 'react-hot-toast';

type WebSocketMessage = {
  type: 'session_ready' | 'turn_result' | 'typing' | 'heartbeat' | 'error';
  [key: string]: any;
};

type WebSocketSendMessage = {
  type: 'user_message' | 'typing' | 'heartbeat';
  content?: string;
  suggested_words?: number[];
  is_typing?: boolean;
};

class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, (data: any) => void> = new Map();
  private connectionStatusHandlers: ((connected: boolean) => void)[] = [];

  constructor(private sessionId: string, private accessToken: string) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/api/v1/sessions/${this.sessionId}/ws?token=${this.accessToken}`;
      
      try {
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.notifyConnectionStatus(true);
          resolve();
        };

        this.socket.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.socket.onclose = (event) => {
          console.log('WebSocket closed:', event.code, event.reason);
          this.stopHeartbeat();
          this.notifyConnectionStatus(false);
          
          if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnect();
          }
        };

        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          toast.error('Connection error occurred');
          reject(error);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        reject(error);
      }
    });
  }

  private reconnect() {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.connect().catch(() => {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          toast.error('Failed to reconnect. Please refresh the page.');
        }
      });
    }, delay);
  }

  private handleMessage(event: MessageEvent) {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      // Handle specific message types
      const handler = this.messageHandlers.get(message.type);
      if (handler) {
        handler(message);
      }
      
      // Handle global message types
      switch (message.type) {
        case 'error':
          toast.error(message.message || 'An error occurred');
          break;
        case 'session_ready':
          console.log('Session ready:', message);
          break;
        default:
          // Let specific handlers deal with the message
          break;
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      this.send({ type: 'heartbeat' });
    }, 30000); // Send heartbeat every 30 seconds
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private notifyConnectionStatus(connected: boolean) {
    this.connectionStatusHandlers.forEach(handler => handler(connected));
  }

  send(message: WebSocketSendMessage) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected. Message not sent:', message);
    }
  }

  sendMessage(content: string, suggestedWords?: number[]) {
    this.send({
      type: 'user_message',
      content,
      suggested_words: suggestedWords,
    });
  }

  sendTyping(isTyping: boolean) {
    this.send({
      type: 'typing',
      is_typing: isTyping,
    });
  }

  onMessage(type: string, handler: (data: any) => void) {
    this.messageHandlers.set(type, handler);
  }

  offMessage(type: string) {
    this.messageHandlers.delete(type);
  }

  onConnectionStatus(handler: (connected: boolean) => void) {
    this.connectionStatusHandlers.push(handler);
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }
    this.messageHandlers.clear();
    this.connectionStatusHandlers.length = 0;
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

// React hook for using WebSocket
export function useWebSocket(sessionId: string) {
  const { data: session } = useSession();
  const wsRef = useRef<WebSocketService | null>(null);
  const connectionStatusRef = useRef<boolean>(false);

  const connect = useCallback(async () => {
    if (!session?.accessToken || !sessionId) return;

    if (wsRef.current) {
      wsRef.current.disconnect();
    }

    wsRef.current = new WebSocketService(sessionId, session.accessToken);
    
    try {
      await wsRef.current.connect();
      connectionStatusRef.current = true;
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      connectionStatusRef.current = false;
    }
  }, [sessionId, session?.accessToken]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
      connectionStatusRef.current = false;
    }
  }, []);

  const sendMessage = useCallback((content: string, suggestedWords?: number[]) => {
    if (wsRef.current) {
      wsRef.current.sendMessage(content, suggestedWords);
    }
  }, []);

  const sendTyping = useCallback((isTyping: boolean) => {
    if (wsRef.current) {
      wsRef.current.sendTyping(isTyping);
    }
  }, []);

  const onMessage = useCallback((type: string, handler: (data: any) => void) => {
    if (wsRef.current) {
      wsRef.current.onMessage(type, handler);
    }
  }, []);

  const isConnected = useCallback(() => {
    return wsRef.current?.isConnected() || false;
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
    sendTyping,
    onMessage,
    isConnected,
    ws: wsRef.current,
  };
}

export default WebSocketService;