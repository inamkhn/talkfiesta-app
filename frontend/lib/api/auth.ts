import axios from "axios";
import { z } from "zod";

// Mirrors backend/app/modules/auth/schemas.py. Auth endpoints do not require
// an access token. Keep this transport independent of the protected API client
// so a rejected refresh cannot recursively invoke its refresh interceptor.
const transport = axios.create({
  baseURL: "/api/v1/auth",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export type LoginInput = { email: string; password: string };
export type RegisterInput = LoginInput & { first_name?: string | null };
export type GoogleInput = { id_token: string };
export type EmailActionInput = { email: string };
export type ActionTokenInput = { token: string };
export type ResetPasswordInput = ActionTokenInput & { new_password: string };

// This summary is deliberately separate from GET /users/me's UserResponse.
const sessionSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().positive(),
  user: z.object({
    id: z.string().uuid(),
    email: z.string(),
    first_name: z.string().nullable(),
    roles: z.array(z.string()),
    onboarding_completed: z.boolean(),
  }),
});
const messageSchema = z.object({ message: z.string() });
export type AuthSessionResponse = z.infer<typeof sessionSchema>;
export type AuthMessageResponse = z.infer<typeof messageSchema>;

async function session(path: string, body?: LoginInput | RegisterInput | GoogleInput): Promise<AuthSessionResponse> {
  const response = await transport.post(path, body);
  return sessionSchema.parse(response.data);
}

async function message(path: string, body: EmailActionInput): Promise<AuthMessageResponse> {
  const response = await transport.post(path, body);
  return messageSchema.parse(response.data);
}

async function empty(path: string, body?: ActionTokenInput | ResetPasswordInput): Promise<void> {
  const response = await transport.post(path, body);
  if (response.status !== 204) throw new Error("Unexpected authentication response.");
}

// Transport only: session locking/storage/cache updates belong to useAuth and
// axios.ts. In particular, application callers must use refreshAccessToken()
// for coordinated rotation and revokeSession()/useAuth.logout() for logout.
export const authApi = {
  register: (input: RegisterInput) => session("/register", input),
  login: (input: LoginInput) => session("/login", input),
  refresh: () => session("/refresh"),
  logout: () => empty("/logout"),
  forgotPassword: (input: EmailActionInput) => message("/forgot-password", input),
  resetPassword: (input: ResetPasswordInput) => empty("/reset-password", input),
  requestEmailVerification: (input: EmailActionInput) => message("/request-email-verification", input),
  verifyEmail: (input: ActionTokenInput) => empty("/verify-email", input),
  googleExchange: (input: GoogleInput) => session("/google/exchange", input),
};
