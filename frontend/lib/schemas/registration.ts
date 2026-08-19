import { z } from "zod";

export const registerDetailsSchema = z.object({
  org_name: z.string().min(1, "Organization name is required").max(200),
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
export type RegisterDetailsForm = z.infer<typeof registerDetailsSchema>;

export const verifyOtpSchema = z.object({
  otp: z
    .string()
    .length(6, "Enter the 6-digit code")
    .regex(/^\d{6}$/, "Digits only"),
});
export type VerifyOtpForm = z.infer<typeof verifyOtpSchema>;
