import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  id: string;
  label: ReactNode;
  error?: string;
  description?: ReactNode;
  required?: boolean;
  className?: string;
  /** Element rendered at the right of the label row, e.g. "Forgot password?". */
  labelAction?: ReactNode;
  children: ReactNode;
}

/**
 * Label + control + help/error text. Pair with react-hook-form `register`:
 *
 * <FormField id="email" label="Email" error={errors.email?.message}>
 *   <Input id="email" aria-invalid={!!errors.email} aria-describedby={fieldDescribedBy("email", errors.email)} {...register("email")} />
 * </FormField>
 */
export function FormField({ id, label, error, description, required, className, labelAction, children }: FormFieldProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id}>
          {label}
          {required && (
            <span className="text-destructive" aria-hidden>
              *
            </span>
          )}
        </Label>
        {labelAction}
      </div>
      {children}
      {description && !error && (
        <p id={`${id}-description`} className="text-xs text-muted-foreground">
          {description}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

/** Returns the `aria-describedby` value matching FormField's help/error ids. */
export function fieldDescribedBy(id: string, error: unknown, hasDescription = false): string | undefined {
  if (error) return `${id}-error`;
  return hasDescription ? `${id}-description` : undefined;
}
