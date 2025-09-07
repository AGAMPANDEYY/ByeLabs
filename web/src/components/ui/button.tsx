import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-2xl text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:-translate-y-0.5",
  {
    variants: {
      variant: {
        default: "bg-primary-600 text-white hover:bg-primary-700 shadow-lg hover:shadow-xl",
        destructive: "bg-rose-600 text-white hover:bg-rose-700 shadow-lg hover:shadow-xl",
        outline: "border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 shadow-lg hover:shadow-xl",
        secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200 shadow-lg hover:shadow-xl",
        ghost: "hover:bg-gray-100 text-gray-600",
        link: "text-primary-600 underline-offset-4 hover:underline",
        gradient: "bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:opacity-90 shadow-lg hover:shadow-xl",
      },
      size: {
        default: "h-12 px-6 py-3",
        sm: "h-9 px-4 py-2 text-xs",
        lg: "h-14 px-8 py-4 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
