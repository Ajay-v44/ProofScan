import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import type { ComponentProps } from "react";
import { twMerge } from "tailwind-merge";

export const buttonVariants = cva("button", {
  variants: { variant: { default: "button-primary", outline: "button-outline", quiet: "button-quiet" } },
  defaultVariants: { variant: "default" },
});

export function Button({ className, variant, type = "button", ...props }: ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return <button type={type} className={twMerge(clsx(buttonVariants({ variant }), className))} {...props} />;
}
