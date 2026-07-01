import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "../store/authStore";
import { useLiveStore } from "../store/liveStore";
import type { WsMessage } from "../types/api";

const BACKOFF_SCHEDULE_MS = [1000, 2000, 5000, 10000, 30000];

export type WsConnectionStatus = "connecting" | "open" | "reconnecting";

/** Connects to /ws/live, feeds every frame into the live store, and reconnects with capped
 * backoff on drop (ARCHITECTURE.md §7, §13 — the dashboard shouldn't just go silent if the
 * WebSocket blips). Mirrors the backend's own PLC reconnect pattern in spirit.
 */
export function useWebSocket(): WsConnectionStatus {
  const accessToken = useAuthStore((state) => state.accessToken);
  const applyWsMessage = useLiveStore((state) => state.applyWsMessage);
  const [status, setStatus] = useState<WsConnectionStatus>("connecting");

  const attemptRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    stoppedRef.current = false;

    function connect() {
      setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Auth is a first-message handshake, not a `?token=` query param — a query-string
      // token would end up verbatim in nginx/proxy access logs and browser history.
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
      socketRef.current = socket;

      socket.onopen = () => {
        socket.send(JSON.stringify({ token: accessToken }));
        attemptRef.current = 0;
        setStatus("open");
      };

      socket.onmessage = (event) => {
        try {
          applyWsMessage(JSON.parse(event.data) as WsMessage);
        } catch {
          // malformed frame — ignore rather than crash the live view
        }
      };

      socket.onclose = () => {
        if (stoppedRef.current) return;
        setStatus("reconnecting");
        const delay = BACKOFF_SCHEDULE_MS[Math.min(attemptRef.current, BACKOFF_SCHEDULE_MS.length - 1)];
        attemptRef.current += 1;
        timeoutRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      stoppedRef.current = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      socketRef.current?.close();
    };
  }, [accessToken, applyWsMessage]);

  return status;
}
