"use client";

import React from "react";
import { motion } from "motion/react";
import { Folder, HeartHandshakeIcon, SparklesIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface DatabaseWithRestApiProps {
  className?: string;
  circleText?: string;
  badgeTexts?: { first: string; second: string; third: string; fourth: string };
  buttonTexts?: { first: string; second: string };
  title?: string;
  lightColor?: string;
}

const DatabaseWithRestApi = ({
  className,
  circleText,
  badgeTexts,
  buttonTexts,
  title,
  lightColor,
}: DatabaseWithRestApiProps) => {
  return (
    <div className={cn("relative flex h-[350px] w-full max-w-[500px] flex-col items-center", className)}>
      {/* SVG — viewBox taller to give badges room */}
      <svg className="h-full sm:w-full text-muted" width="100%" height="100%" viewBox="0 0 200 108">
        {/* Connector paths — start at y=18 (badge bottom) */}
        <g stroke="currentColor" fill="none" strokeWidth="0.4" strokeDasharray="100 100" pathLength="100">
          <path d="M 28 18 v 13 q 0 5 5 5 h 62 q 5 0 5 5 v 10" />
          <path d="M 78 18 v 8  q 0 5 5 5 h 12 q 5 0 5 5 v 10" />
          <path d="M 125 18 v 8  q 0 5 -5 5 h -14 q -5 0 -5 5 v 10" />
          <path d="M 172 18 v 13 q 0 5 -5 5 h -62 q -5 0 -5 5 v 10" />
          <animate attributeName="stroke-dashoffset" from="100" to="0" dur="1s" fill="freeze"
            calcMode="spline" keySplines="0.25,0.1,0.5,1" keyTimes="0; 1" />
        </g>

        {/* Animated glow orbs */}
        <g mask="url(#db-mask-1)">
          <circle className="database db-light-1" cx="0" cy="0" r="20" fill="url(#db-green-grad)" />
        </g>
        <g mask="url(#db-mask-2)">
          <circle className="database db-light-2" cx="0" cy="0" r="20" fill="url(#db-green-grad)" />
        </g>
        <g mask="url(#db-mask-3)">
          <circle className="database db-light-3" cx="0" cy="0" r="20" fill="url(#db-green-grad)" />
        </g>
        <g mask="url(#db-mask-4)">
          <circle className="database db-light-4" cx="0" cy="0" r="20" fill="url(#db-green-grad)" />
        </g>

        {/* Badges — centered text, no icon */}
        <g stroke="currentColor" fill="none" strokeWidth="0.4">
          {/* Badge 1: center x=28 */}
          <g>
            <rect fill="#18181B" x="4"   y="2" width="48" height="14" rx="6" />
            <text x="28"  y="12" textAnchor="middle" fill="white" stroke="none" fontSize="5.5" fontWeight="600">{badgeTexts?.first  ?? "GET"}</text>
          </g>
          {/* Badge 2: center x=78 */}
          <g>
            <rect fill="#18181B" x="55"  y="2" width="46" height="14" rx="6" />
            <text x="78"  y="12" textAnchor="middle" fill="white" stroke="none" fontSize="5.5" fontWeight="600">{badgeTexts?.second ?? "POST"}</text>
          </g>
          {/* Badge 3: center x=125 */}
          <g>
            <rect fill="#18181B" x="103" y="2" width="44" height="14" rx="6" />
            <text x="125" y="12" textAnchor="middle" fill="white" stroke="none" fontSize="5.5" fontWeight="600">{badgeTexts?.third  ?? "PUT"}</text>
          </g>
          {/* Badge 4: center x=172 */}
          <g>
            <rect fill="#18181B" x="149" y="2" width="47" height="14" rx="6" />
            <text x="172" y="12" textAnchor="middle" fill="white" stroke="none" fontSize="5.5" fontWeight="600">{badgeTexts?.fourth ?? "DELETE"}</text>
          </g>
        </g>

        <defs>
          <mask id="db-mask-1">
            <path d="M 28 18 v 13 q 0 5 5 5 h 62 q 5 0 5 5 v 10" strokeWidth="0.8" stroke="white" />
          </mask>
          <mask id="db-mask-2">
            <path d="M 78 18 v 8  q 0 5 5 5 h 12 q 5 0 5 5 v 10" strokeWidth="0.8" stroke="white" />
          </mask>
          <mask id="db-mask-3">
            <path d="M 125 18 v 8  q 0 5 -5 5 h -14 q -5 0 -5 5 v 10" strokeWidth="0.8" stroke="white" />
          </mask>
          <mask id="db-mask-4">
            <path d="M 172 18 v 13 q 0 5 -5 5 h -62 q -5 0 -5 5 v 10" strokeWidth="0.8" stroke="white" />
          </mask>
          <radialGradient id="db-green-grad" fx="0.5" fy="0.5">
            <stop offset="0%"   stopColor={lightColor ?? "#4ade80"} stopOpacity="1" />
            <stop offset="40%"  stopColor={lightColor ?? "#4ade80"} stopOpacity="0.6" />
            <stop offset="100%" stopColor="transparent" stopOpacity="0" />
          </radialGradient>
        </defs>
      </svg>

      {/* Main Box */}
      <div className="absolute bottom-10 flex w-full flex-col items-center">
        <div className="absolute -bottom-4 h-[100px] w-[62%] rounded-lg bg-accent/30" />
        <div className="absolute -top-3 z-20 flex items-center justify-center rounded-lg border bg-[#101112] px-2 py-1 sm:-top-4 sm:py-1.5">
          <SparklesIcon className="size-3" />
          <span className="ml-2 text-[10px]">{title ?? "Satellite · Weather · AI Agent → Zero Crop Loss"}</span>
        </div>
        <div className="absolute -bottom-8 z-30 grid h-[60px] w-[60px] place-items-center rounded-full border-t bg-[#141516] font-semibold text-xs">
          {circleText ?? "AI"}
        </div>
        <div className="relative z-10 flex h-[150px] w-full items-center justify-center overflow-hidden rounded-lg border bg-background shadow-md">
          <div className="absolute bottom-8 left-12 z-10 h-7 rounded-full bg-[#101112] px-3 text-xs border flex items-center gap-2">
            <HeartHandshakeIcon className="size-4" />
            <span>{buttonTexts?.first ?? "Harvest ready"}</span>
          </div>
          <div className="absolute right-16 z-10 hidden h-7 rounded-full bg-[#101112] px-3 text-xs sm:flex border items-center gap-2">
            <Folder className="size-4" />
            <span>{buttonTexts?.second ?? "Rain in 36h"}</span>
          </div>
          <motion.div className="absolute -bottom-14 h-[100px] w-[100px] rounded-full border-t bg-accent/5"
            animate={{ scale: [0.98, 1.02, 0.98, 1, 1, 1, 1, 1, 1] }} transition={{ duration: 2, repeat: Infinity }} />
          <motion.div className="absolute -bottom-20 h-[145px] w-[145px] rounded-full border-t bg-accent/5"
            animate={{ scale: [1, 1, 1, 0.98, 1.02, 0.98, 1, 1, 1] }} transition={{ duration: 2, repeat: Infinity }} />
          <motion.div className="absolute -bottom-[100px] h-[190px] w-[190px] rounded-full border-t bg-accent/5"
            animate={{ scale: [1, 1, 1, 1, 1, 0.98, 1.02, 0.98, 1, 1] }} transition={{ duration: 2, repeat: Infinity }} />
          <motion.div className="absolute -bottom-[120px] h-[235px] w-[235px] rounded-full border-t bg-accent/5"
            animate={{ scale: [1, 1, 1, 1, 1, 1, 0.98, 1.02, 0.98, 1] }} transition={{ duration: 2, repeat: Infinity }} />
        </div>
      </div>
    </div>
  );
};

export default DatabaseWithRestApi;
