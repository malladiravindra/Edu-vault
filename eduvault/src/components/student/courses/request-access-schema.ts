import { z } from "zod";

export const requestAccessSchema = z.object({
  message: z.string().trim().max(500, "Keep your message under 500 characters"),
});

export type RequestAccessValues = z.infer<typeof requestAccessSchema>;
