import * as React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Utility to merge tailwind classes */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "secondary" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  asChild?: boolean;
}

const buttonVariants = {
  base: "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-green focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]",
  variants: {
    variant: {
      default: "bg-gradient-to-b from-brand-green to-[#135234] text-white shadow-[0_4px_14px_0_rgba(26,107,69,0.39)] hover:shadow-[0_6px_20px_rgba(26,107,69,0.23)] hover:-translate-y-0.5",
      primary: "bg-gradient-to-b from-[#F7974E] to-brand-orange text-white shadow-[0_4px_14px_0_rgba(244,131,42,0.39)] hover:shadow-[0_6px_20px_rgba(244,131,42,0.23)] hover:-translate-y-0.5 border border-[#e6751c]",
      secondary: "bg-white text-gray-900 shadow-sm border border-gray-200 hover:bg-gray-50 hover:shadow-md hover:-translate-y-0.5",
      outline: "border-2 border-brand-green/20 bg-transparent text-brand-green hover:bg-brand-green/5",
      ghost: "hover:bg-brand-green/10 hover:text-brand-green text-gray-600",
    },
    size: {
      default: "h-10 px-4 py-2",
      sm: "h-9 rounded-md px-3",
      lg: "h-11 rounded-md px-8 text-base",
      icon: "h-10 w-10",
    },
  },
  defaultVariants: {
    variant: "default",
    size: "default",
  },
} as const;

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        className={cn(
          buttonVariants.base,
          buttonVariants.variants.variant[variant],
          buttonVariants.variants.size[size],
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
