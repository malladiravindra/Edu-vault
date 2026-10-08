import { toast } from "sonner";
import { getErrorMessage } from "@/lib/api/client";

/**
 * Thin wrapper over sonner so feedback copy and behaviour stay consistent.
 *   notify.success("Course published")
 *   notify.error(error, "Couldn't publish course")
 */
export const notify = {
  success: (message: string, description?: string) => toast.success(message, { description }),
  info: (message: string, description?: string) => toast.info(message, { description }),
  warning: (message: string, description?: string) => toast.warning(message, { description }),
  error: (error: unknown, title = "Something went wrong") => toast.error(title, { description: getErrorMessage(error) }),
};
