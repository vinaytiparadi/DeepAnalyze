"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { consumeTransfer, type TransferData } from "@/lib/transfer-store";
import { stopGeneration, getSession } from "@/lib/api";
import { AnalyzePage, type SessionSnapshot } from "@/components/analyze-page";

function AnalyzeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const tid = searchParams.get("tid");
  const urlId = searchParams.get("id");

  // Derive active sessionId: prefer ID from URL, then tid-based persistence
  const activeSessionId = useMemo(() => {
    if (urlId) return urlId;
    if (!tid) return `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const key = `session:${tid}`;
    try {
      const existing = sessionStorage.getItem(key);
      if (existing) return existing;
    } catch { /* noop */ }
    const id = `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    try { sessionStorage.setItem(key, id); } catch { /* noop */ }
    return id;
  }, [tid, urlId]);

  // Keep a dictionary of all sessions loaded in this browser tab
  const [sessions, setSessions] = useState<Record<string, {
    transfer: TransferData;
    recoverySnapshot: SessionSnapshot | null;
  }>>({});
  
  // Track which sessions are currently being fetched from backend/storage
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    // If the active session is already loaded or is currently loading, do nothing
    if (!activeSessionId || sessions[activeSessionId] || loadingIds.has(activeSessionId)) {
      return;
    }

    const redirectToHome = () => {
      router.replace("/");
    };

    async function initialize() {
      setLoadingIds(prev => new Set(prev).add(activeSessionId));

      let loadedTransfer: TransferData | null = null;
      let loadedSnapshot: SessionSnapshot | null = null;

      // 1. If we have a direct sessionId from URL, try to load it from backend
      if (urlId) {
        try {
          const detail = await getSession(urlId);
          loadedTransfer = {
            prompt: detail.title,
            files: [], 
            reportTheme: detail.report_theme || "literature",
            presetId: null,
            planRouterEnabled: true,
            engine: detail.engine || "deepanalyze"
          };
          
          loadedSnapshot = {
            prompt: detail.title,
            reportTheme: detail.report_theme || "literature",
            presetId: null,
            phase: "complete",
            accumulatedContent: detail.messages.length > 0 ? detail.messages[detail.messages.length - 1].content : "",
            completedTurns: detail.messages.slice(0, -1).reduce((acc, m, i, arr) => {
               if (m.role === "user") {
                 const next = arr[i+1];
                 acc.push({ role: "user", content: m.content });
                 if (next && next.role === "assistant") {
                    acc.push({ role: "assistant", content: next.content });
                 }
               }
               return acc;
            }, [] as any[]),
            messages: detail.messages,
            workspaceFileNames: [], 
            plan: detail.plan,
            engine: detail.engine || "deepanalyze",
          };
        } catch (err) {
          console.error("Failed to load session from backend:", err);
        }
      }

      if (!loadedTransfer && !tid && !urlId) {
        redirectToHome();
        return;
      }

      // 2. Check for a session snapshot in sessionStorage (if not loaded from backend)
      if (!loadedTransfer) {
        try {
          const raw = sessionStorage.getItem(`snapshot:${activeSessionId}`);
          if (raw) {
            const snap: SessionSnapshot = JSON.parse(raw);
            if (snap.phase === "streaming") {
              stopGeneration(activeSessionId).catch(() => {});
            }
            loadedTransfer = { 
              prompt: snap.prompt, 
              files: [], 
              reportTheme: snap.reportTheme, 
              presetId: snap.presetId, 
              planRouterEnabled: snap.planRouterEnabled ?? false, 
              engine: snap.engine ?? "deepanalyze" 
            };
            loadedSnapshot = snap;
          }
        } catch { /* noop */ }
      }

      // 3. Normal path: consume transfer data
      if (!loadedTransfer) {
        const data = consumeTransfer(tid || "");
        if (!data) {
          if (!urlId) redirectToHome();
          setLoadingIds(prev => {
            const next = new Set(prev);
            next.delete(activeSessionId);
            return next;
          });
          return;
        }
        loadedTransfer = data;
      }

      // Commit to state
      if (loadedTransfer) {
        setSessions(prev => ({
          ...prev,
          [activeSessionId]: {
            transfer: loadedTransfer as TransferData,
            recoverySnapshot: loadedSnapshot
          }
        }));
      }

      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(activeSessionId);
        return next;
      });
    }

    initialize();
  }, [activeSessionId, sessions, loadingIds, tid, urlId, router]);

  return (
    <>
      {loadingIds.has(activeSessionId) && (
        <div className="relative flex h-[100dvh] items-center justify-center bg-background overflow-hidden">
          <div className="absolute inset-0 z-0 pointer-events-none opacity-[0.03] dark:opacity-[0.06] bg-[url('https://www.transparenttextures.com/patterns/stardust.png')] mix-blend-overlay" />
          <div className="flex flex-col items-center gap-4 z-10">
            <div className="w-8 h-8 border border-primary/20 border-t-primary rounded-full animate-spin" />
            <div className="font-mono text-[10px] text-primary uppercase tracking-[0.3em] font-medium drop-shadow-[0_0_10px_rgba(var(--primary),0.3)]">
              Initializing Session
            </div>
          </div>
        </div>
      )}

      {Object.entries(sessions).map(([id, sessionData]) => (
        <div
          key={id}
          className="w-full h-[100dvh]"
          style={{ display: id === activeSessionId && !loadingIds.has(activeSessionId) ? 'block' : 'none' }}
        >
          <AnalyzePage
            prompt={sessionData.transfer.prompt}
            files={sessionData.transfer.files}
            reportTheme={sessionData.transfer.reportTheme}
            presetId={sessionData.transfer.presetId}
            planningEnabled={sessionData.transfer.planRouterEnabled}
            routerEnabled={sessionData.transfer.planRouterEnabled}
            engine={sessionData.transfer.engine}
            sessionId={id}
            recoverySnapshot={sessionData.recoverySnapshot}
          />
        </div>
      ))}
    </>
  );
}

export default function AnalyzeRoute() {
  return (
    <Suspense
      fallback={
        <div className="relative flex h-[100dvh] items-center justify-center bg-background overflow-hidden">
          <div className="absolute inset-0 z-0 pointer-events-none opacity-[0.03] dark:opacity-[0.06] bg-[url('https://www.transparenttextures.com/patterns/stardust.png')] mix-blend-overlay" />
          <div className="flex flex-col items-center gap-4 z-10">
            <div className="w-8 h-8 border border-primary/20 border-t-primary rounded-full animate-spin" />
            <div className="font-mono text-[10px] text-primary uppercase tracking-[0.3em] font-medium">
              Loading Route
            </div>
          </div>
        </div>
      }
    >
      <AnalyzeContent />
    </Suspense>
  );
}
