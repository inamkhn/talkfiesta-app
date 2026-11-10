import { z } from "zod";
import apiClient from "./axios";

const ticketSchema = z.object({ upload_id: z.string().uuid(), upload_url: z.string().url(), method: z.literal("PUT"), headers: z.record(z.string(), z.string()), expires_at: z.string().datetime({ offset: true }) });
export type AudioTicket = z.infer<typeof ticketSchema>;
export async function allocateAssessmentAudio(responseId: string, blob: Blob, signal: AbortSignal): Promise<AudioTicket> {
  if (!crypto.subtle) throw new Error("Audio upload requires a secure HTTPS connection.");
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
  const checksum = btoa(String.fromCharCode(...digest));
  const response = await apiClient.post("/media/audio-uploads", {
    purpose: "ASSESSMENT", assessment_response_id: responseId,
    content_type: blob.type.split(";")[0], size_bytes: blob.size, checksum_sha256: checksum,
  }, { signal });
  return ticketSchema.parse(response.data);
}
export async function confirmAssessmentAudio(ticket: AudioTicket, responseId: string, signal: AbortSignal): Promise<void> {
  const response = await apiClient.post(`/media/audio-uploads/${ticket.upload_id}/confirm`, null, { signal });
  const confirmed = z.object({ upload_id: z.string().uuid(), assessment_response_id: z.string().uuid(), status: z.literal("VERIFIED") }).parse(response.data);
  if (confirmed.upload_id !== ticket.upload_id || confirmed.assessment_response_id !== responseId) throw new Error("The recording confirmation did not match this question.");
}
