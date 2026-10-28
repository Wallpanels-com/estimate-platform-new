import { lazy, Suspense } from "react";
import { useAuth } from "../lib/auth";

const FeedbackToolbar = lazy(() => import("./FeedbackToolbar"));

export default function StaffFeedback() {
  const { token, user, loading } = useAuth();
  if (!token || loading || !user?.is_active || !user.agentation_enabled)
    return null;
  return (
    <Suspense fallback={null}>
      <FeedbackToolbar key={user.id} />
    </Suspense>
  );
}
