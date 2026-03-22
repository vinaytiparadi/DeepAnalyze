"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { DitheringBackground } from "@/components/ui/dithering-background";
import { TextScramble } from "@/components/ui/text-scrammble";
import { ThemeToggle } from "@/components/theme-toggle";
import { PromptInputEnhanced } from "@/components/prompt-input-enhanced";
import { PresetSelector } from "@/components/preset-selector";
import { CUPCAKE_URL } from "@/lib/config";

const ease = [0.22, 1, 0.36, 1] as const;

export default function Home() {
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [reportTheme, setReportTheme] = useState("modern");
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);

  const handlePresetSelect = (presetId: string, promptText: string) => {
    setSelectedPresetId(presetId);
    setInput(promptText);
  };

  const handleAnalyze = () => {
    if (!input.trim() && files.length === 0) return;
    const params = new URLSearchParams();
    if (input.trim()) params.set("prompt", input.trim());
    params.set("reportTheme", reportTheme);
    if (selectedPresetId) params.set("preset", selectedPresetId);
    window.location.href = `${CUPCAKE_URL}?${params.toString()}`;
  };

  return (
    <main className="relative h-screen w-screen overflow-hidden">
      {/* 3D dithering shader background */}
      <DitheringBackground />

      {/* Theme toggle */}
      <div className="absolute top-5 right-5 z-20">
        <ThemeToggle />
      </div>

      {/* Hero — single composition */}
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-6 gap-8">
        {/* Brand */}
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease }}
          className="select-none"
        >
          <h1
            className="font-display font-extrabold tracking-[-0.03em] text-[clamp(4.5rem,12vw,9rem)] leading-[0.85] text-center"
            style={{
              background: "var(--brand-gradient)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Autolytics
          </h1>
        </motion.div>

        {/* Tagline */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="flex justify-center"
        >
          <TextScramble
            phrases={[
              "Autonomous Data Science",
              "Upload. Analyze. Discover.",
              "From Data to Decisions",
            ]}
            pauseMs={2500}
            loop
            autoStart
            textClass="font-display font-semibold tracking-[-0.01em] text-[clamp(1.15rem,2.4vw,1.65rem)] text-muted-foreground text-center"
            dudClass="text-muted-foreground/25"
          />
        </motion.div>

        {/* Prompt input — the visual anchor */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.55, ease }}
          className="w-full max-w-2xl mt-2"
        >
          <PromptInputEnhanced
            input={input}
            onInputChange={setInput}
            files={files}
            onFilesChange={setFiles}
            reportTheme={reportTheme}
            onReportThemeChange={setReportTheme}
            isLoading={false}
            onSubmit={handleAnalyze}
          />
        </motion.div>

        {/* Preset hints */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.75 }}
          className="w-full max-w-2xl"
        >
          <PresetSelector
            selectedId={selectedPresetId}
            onSelect={handlePresetSelect}
          />
        </motion.div>
      </div>
    </main>
  );
}
