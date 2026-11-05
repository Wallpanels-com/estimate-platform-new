import { ApiError, request, post } from "./api";
export type Evidence = { text: string; question: string; answer: string };
export type Review = {
  content: {
    summary: string;
    experience: string;
    strengths: Evidence[];
    gaps: Evidence[];
    interview_questions: string[];
    message_uk: string;
  };
  message_draft: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  stale: boolean;
};
export type ReviewResult = { enabled: boolean; review: Review | null };
export async function loadCandidateReview(id: string): Promise<ReviewResult> {
  const path = `/hr/candidates/${id}/ai`;
  const saved = await request<ReviewResult>(path);
  if (!saved.enabled || (saved.review && !saved.review.stale)) return saved;
  try {
    // The backend reuses an unchanged saved review and serializes concurrent requests.
    return await post<ReviewResult>(path, { refresh: false });
  } catch (error) {
    if (
      !(error instanceof ApiError) ||
      error.status !== 409 ||
      !error.message.includes("already being prepared")
    )
      throw error;
    // Another tab/user already started this candidate. Wait for their result;
    // never issue another generation request while that work is running.
    for (let i = 0; i < 26; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const result = await request<ReviewResult>(path);
      if (result.review && !result.review.stale) return result;
    }
    throw error;
  }
}
