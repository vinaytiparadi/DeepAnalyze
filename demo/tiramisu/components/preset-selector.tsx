"use client";

import { DATA_ANALYSIS_PROMPT_PRESETS } from "@/lib/prompt-presets";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface PresetSelectorProps {
  selectedId: string | null;
  onSelect: (presetId: string, promptText: string) => void;
}

export function PresetSelector({ selectedId, onSelect }: PresetSelectorProps) {
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-2 text-sm">
        <span className="text-muted-foreground/60 mr-1.5 select-none">
          Try:
        </span>
        {DATA_ANALYSIS_PROMPT_PRESETS.map((preset, i) => (
          <span key={preset.id} className="inline-flex items-center">
            {i > 0 && (
              <span
                className="text-border mx-1.5 select-none"
                aria-hidden="true"
              >
                ·
              </span>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => onSelect(preset.id, preset.prompt.en)}
                  className={cn(
                    "text-muted-foreground transition-colors duration-150 hover:text-primary",
                    selectedId === preset.id && "text-primary font-medium"
                  )}
                >
                  {preset.label.en}
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[250px]">
                <p className="text-sm">{preset.description.en}</p>
              </TooltipContent>
            </Tooltip>
          </span>
        ))}
      </div>
    </TooltipProvider>
  );
}
