"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Edit2, 
  Check, 
  X,
  MoreVertical,
  History,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings as SettingsIcon,
  Github
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { listSessions, deleteSession, updateSessionTitle, type Session } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentSessionId = searchParams.get("id");
  
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const refreshSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
    // Refresh periodically
    const interval = setInterval(refreshSessions, 10000);
    return () => clearInterval(interval);
  }, [refreshSessions]);

  const handleNewChat = () => {
    router.push("/");
  };

  const handleSelectSession = (id: string) => {
    router.push(`/analyze?id=${id}`);
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat?")) return;
    try {
      await deleteSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
      if (currentSessionId === id) {
        router.push("/");
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  const startEditing = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
  };

  const handleRename = async (e: React.FormEvent, id: string) => {
    e.preventDefault();
    if (!editTitle.trim()) return;
    try {
      await updateSessionTitle(id, editTitle);
      setSessions(prev => prev.map(s => s.id === id ? { ...s, title: editTitle } : s));
      setEditingId(null);
    } catch (error) {
      console.error("Failed to rename session:", error);
    }
  };

  const filteredSessions = sessions.filter(s => 
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      {/* Mobile Toggle */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-3 left-4 z-50 p-2 lg:hidden text-muted-foreground hover:text-foreground bg-background/80 backdrop-blur-md border border-border/20"
      >
        {isOpen ? <X className="size-4" /> : <PanelLeftOpen className="size-4" />}
      </button>

      {/* Desktop Toggle Button (when closed) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed top-1/2 left-0 -translate-y-1/2 z-50 p-1 bg-background/80 backdrop-blur-md border border-l-0 border-border/20 rounded-r-md hidden lg:block text-muted-foreground hover:text-primary transition-colors"
        >
          <PanelLeftOpen className="size-4" />
        </button>
      )}

      <AnimatePresence mode="wait">
        {isOpen && (
          <motion.div
            initial={{ x: -300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -300, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 left-0 z-40 w-[280px] bg-background/60 backdrop-blur-xl border-r border-border/10 flex flex-col shadow-2xl"
          >
            {/* Header */}
            <div className="p-4 flex items-center justify-between border-b border-border/5">
              <div className="flex items-center gap-2 cursor-pointer" onClick={() => router.push("/")}>
                <span className="font-display font-medium text-lg tracking-tight text-foreground lowercase">
                  <span className="text-primary italic">sway</span>lytics<span className="text-primary font-bold italic">.</span>
                </span>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-muted-foreground/60 hover:text-foreground transition-colors lg:block hidden"
              >
                <PanelLeftClose className="size-4" />
              </button>
            </div>

            {/* Action Bar */}
            <div className="p-4 space-y-3">
              <Button 
                onClick={handleNewChat}
                className="w-full justify-start gap-2.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-none h-11 transition-all group"
              >
                <Plus className="size-4 group-hover:rotate-90 transition-transform duration-300" />
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] font-bold">New_Analysis</span>
              </Button>

              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground/40 group-focus-within:text-primary/60 transition-colors" />
                <input 
                  type="text"
                  placeholder="Search chats..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-background/40 border border-border/20 rounded-none h-9 pl-9 pr-4 text-[12px] font-medium placeholder:text-muted-foreground/30 focus:outline-none focus:border-primary/40 transition-colors"
                />
              </div>
            </div>

            {/* Session List */}
            <div className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin">
              <div className="mb-2 px-2 flex items-center gap-2">
                <History className="size-3 text-muted-foreground/40" />
                <span className="font-mono text-[8px] uppercase tracking-[0.25em] text-muted-foreground/60 font-bold">Recent_History</span>
              </div>

              <div className="space-y-0.5">
                {isLoading && sessions.length === 0 ? (
                  <div className="py-10 flex flex-col items-center gap-3">
                    <div className="size-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
                  </div>
                ) : filteredSessions.length === 0 ? (
                  <div className="py-10 text-center">
                    <p className="font-mono text-[9px] text-muted-foreground/40 uppercase tracking-[0.2em]">No history found</p>
                  </div>
                ) : (
                  filteredSessions.map((session) => (
                    <div 
                      key={session.id}
                      onClick={() => handleSelectSession(session.id)}
                      className={cn(
                        "group relative flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-all duration-200 border-l-2",
                        currentSessionId === session.id 
                          ? "bg-primary/[0.08] border-primary text-foreground" 
                          : "bg-transparent border-transparent hover:bg-muted/30 hover:border-border/40 text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <MessageSquare className={cn(
                        "size-3.5 flex-shrink-0 transition-colors",
                        currentSessionId === session.id ? "text-primary" : "text-muted-foreground/30 group-hover:text-muted-foreground/60"
                      )} />
                      
                      {editingId === session.id ? (
                        <form onSubmit={(e) => handleRename(e, session.id)} className="flex-1 flex items-center gap-1" onClick={e => e.stopPropagation()}>
                          <input 
                            autoFocus
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onBlur={() => setEditingId(null)}
                            className="w-full bg-background border border-primary/30 px-1.5 py-0.5 text-[12px] focus:outline-none"
                          />
                          <button type="submit" className="p-1 hover:text-primary"><Check className="size-3" /></button>
                        </form>
                      ) : (
                        <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                          <p className="text-[12px] font-medium truncate leading-tight">{session.title}</p>
                          <div className="flex items-center gap-2">
                             <span className="font-mono text-[8px] uppercase tracking-tighter opacity-40">
                               {new Date(session.updated_at * 1000).toLocaleDateString()}
                             </span>
                             {session.engine === "gemini" && (
                               <span className="font-mono text-[7px] bg-primary/10 text-primary/60 px-1 uppercase tracking-tighter">Gemini</span>
                             )}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className={cn(
                        "flex items-center gap-1 transition-opacity",
                        currentSessionId === session.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                      )}>
                        <button 
                          onClick={(e) => startEditing(e, session)}
                          className="p-1.5 hover:text-primary hover:bg-primary/10 transition-colors"
                          title="Rename"
                        >
                          <Edit2 className="size-3" />
                        </button>
                        <button 
                          onClick={(e) => handleDeleteSession(e, session.id)}
                          className="p-1.5 hover:text-destructive hover:bg-destructive/10 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 mt-auto border-t border-border/5 space-y-4">
              <div className="flex items-center justify-between">
                <ThemeToggle />
                <div className="flex items-center gap-2">
                   <a href="#" className="p-1.5 text-muted-foreground/40 hover:text-foreground transition-colors"><SettingsIcon className="size-4" /></a>
                   <a href="https://github.com/heywhale/DeepAnalyze" target="_blank" rel="noreferrer" className="p-1.5 text-muted-foreground/40 hover:text-foreground transition-colors"><Github className="size-4" /></a>
                </div>
              </div>
              <div className="flex items-center gap-3 px-1">
                <div className="size-8 rounded-none bg-gradient-to-br from-primary to-primary-foreground flex items-center justify-center text-[10px] font-bold text-white font-mono">
                  DA
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-bold leading-none">v0.4.2-alpha</span>
                  <span className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest mt-1">DeepAnalyze Engine</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-background/20 backdrop-blur-sm z-30 lg:hidden"
        />
      )}
    </>
  );
}
