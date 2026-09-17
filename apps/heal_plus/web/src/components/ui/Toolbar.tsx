"use client";

import {
  Edit2,
  Lock,
  type LucideIcon,
  MousePointer2,
  Move,
  RotateCcw,
  Sparkles,
  Target,
  Trash2,
  FileDown,
  Layers,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import * as React from "react";
import { cn } from "../../lib/utils";

export interface ToolbarItem {
  id: string;
  title: string;
  icon: LucideIcon;
  badge?: string | number;
}

export interface ToolbarProps {
  items?: ToolbarItem[];
  defaultSelected?: string | null;
  selected?: string | null;
  className?: string;
  activeColor?: string;
  onSelect?: (itemId: string) => void;
  showToggle?: boolean;
  toggleState?: boolean;
  toggleLabelOn?: string;
  toggleLabelOff?: string;
  onToggleChange?: (toggled: boolean) => void;
}

export const DEFAULT_ANALYZER_TOOLBAR_ITEMS: ToolbarItem[] = [
  { id: "select", title: "Selecionar ROI", icon: Target },
  { id: "pan", title: "Navegar / Pan", icon: Move },
  { id: "clear", title: "Limpar ROIs", icon: Trash2 },
  { id: "reset", title: "Resetar Visão", icon: RotateCcw },
  { id: "analyze", title: "Analisar", icon: Sparkles },
];

const buttonVariants = {
  initial: {
    gap: 0,
    paddingLeft: ".5rem",
    paddingRight: ".5rem",
  },
  animate: (isSelected: boolean) => ({
    gap: isSelected ? ".375rem" : 0,
    paddingLeft: isSelected ? "0.75rem" : ".5rem",
    paddingRight: isSelected ? "0.75rem" : ".5rem",
  }),
};

const spanVariants = {
  initial: { width: 0, opacity: 0 },
  animate: { width: "auto", opacity: 1 },
  exit: { width: 0, opacity: 0 },
};

const notificationVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: -8 },
  exit: { opacity: 0, y: -16 },
};

const lineVariants = {
  initial: { scaleX: 0, x: "-50%" },
  animate: {
    scaleX: 1,
    x: "0%",
    transition: { duration: 0.2, ease: "easeOut" },
  },
  exit: {
    scaleX: 0,
    x: "50%",
    transition: { duration: 0.2, ease: "easeIn" },
  },
};

const transition = { type: "spring", bounce: 0, duration: 0.35 };

export function Toolbar({
  items = DEFAULT_ANALYZER_TOOLBAR_ITEMS,
  defaultSelected = "select",
  selected: externalSelected,
  className,
  onSelect,
  showToggle = false,
  toggleState = false,
  toggleLabelOn = "Bloqueado",
  toggleLabelOff = "Livre",
  onToggleChange,
}: ToolbarProps) {
  const [internalSelected, setInternalSelected] = React.useState<string | null>(
    defaultSelected
  );

  const selected = externalSelected !== undefined ? externalSelected : internalSelected;
  const [isToggled, setIsToggled] = React.useState(toggleState);
  const [activeNotification, setActiveNotification] = React.useState<string | null>(null);

  React.useEffect(() => {
    setIsToggled(toggleState);
  }, [toggleState]);

  const handleItemClick = (itemId: string) => {
    if (externalSelected === undefined) {
      setInternalSelected(selected === itemId ? null : itemId);
    }
    onSelect?.(itemId);
    setActiveNotification(itemId);
    setTimeout(() => setActiveNotification(null), 1400);
  };

  const handleToggleClick = () => {
    const nextState = !isToggled;
    setIsToggled(nextState);
    onToggleChange?.(nextState);
  };

  return (
    <div className="space-y-1.5 select-none">
      <div
        className={cn(
          "relative flex items-center gap-1.5 p-1.5",
          "bg-white dark:bg-[#0c0c0e]",
          "rounded-2xl border border-heal-line/80 dark:border-zinc-800",
          "shadow-soft transition-all duration-200",
          className
        )}
      >
        <AnimatePresence>
          {activeNotification && (
            <motion.div
              animate="animate"
              className="absolute -top-7 left-1/2 z-50 -translate-x-1/2 transform pointer-events-none"
              exit="exit"
              initial="initial"
              transition={{ duration: 0.25 }}
              variants={notificationVariants as any}
            >
              <div className="rounded-full bg-heal-ink dark:bg-white px-2.5 py-0.5 text-white dark:text-heal-ink text-[11px] font-bold shadow-md">
                {items.find((item) => item.id === activeNotification)?.title || activeNotification}
              </div>
              <motion.div
                animate="animate"
                className="absolute -bottom-0.5 left-1/2 h-[2px] w-full origin-left bg-heal-blue"
                exit="exit"
                initial="initial"
                variants={lineVariants as any}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
          {items.map((item) => {
            const isSelected = selected === item.id;
            return (
              <motion.button
                animate="animate"
                className={cn(
                  "relative flex items-center rounded-xl px-2.5 py-1.5 border-0 cursor-pointer",
                  "font-bold text-xs transition-colors duration-200 shrink-0",
                  isSelected
                    ? "bg-heal-blue text-slate-950 shadow-sm"
                    : "text-heal-muted dark:text-zinc-400 hover:bg-heal-canvas dark:hover:bg-zinc-800/60 hover:text-heal-ink dark:hover:text-white"
                )}
                custom={isSelected}
                initial={false}
                key={item.id}
                onClick={() => handleItemClick(item.id)}
                transition={transition as any}
                type="button"
                variants={buttonVariants as any}
              >
                <item.icon
                  className={cn("h-4 w-4 shrink-0", isSelected ? "text-white" : "text-heal-blue")}
                />
                <AnimatePresence initial={false}>
                  {isSelected && (
                    <motion.span
                      animate="animate"
                      className="overflow-hidden whitespace-nowrap text-xs"
                      exit="exit"
                      initial="initial"
                      transition={transition as any}
                      variants={spanVariants as any}
                    >
                      {item.title}
                    </motion.span>
                  )}
                </AnimatePresence>
                {item.badge !== undefined && (
                  <span className={cn(
                    "ml-1.5 rounded-full px-1.5 py-0.2 text-[10px] font-black",
                    isSelected ? "bg-white/20 text-white" : "bg-heal-softBlue text-heal-blue dark:bg-blue-950/40"
                  )}>
                    {item.badge}
                  </span>
                )}
              </motion.button>
            );
          })}

          {showToggle && (
            <motion.button
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 cursor-pointer ml-1",
                "rounded-xl border shadow-xs transition-all duration-200 border-0",
                isToggled
                  ? "bg-heal-blue text-slate-950 hover:bg-heal-blueDark"
                  : "bg-heal-canvas dark:bg-zinc-900 text-heal-muted dark:text-zinc-400 hover:bg-slate-200 dark:hover:bg-zinc-800 hover:text-heal-ink dark:hover:text-white"
              )}
              onClick={handleToggleClick}
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {isToggled ? (
                <Lock className="h-3.5 w-3.5" />
              ) : (
                <Edit2 className="h-3.5 w-3.5" />
              )}
              <span className="font-bold text-xs whitespace-nowrap">
                {isToggled ? toggleLabelOn : toggleLabelOff}
              </span>
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
}

export default Toolbar;
