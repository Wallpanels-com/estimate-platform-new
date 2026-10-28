import { lazy, Suspense } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

const FeedbackToolbar = lazy(() => import("./FeedbackToolbar"));

export default function StaffFeedback() {
  const { token, user, loading } = useAuth();
  const { pathname } = useLocation();
  if (!token || loading || !user?.is_active || !user.agentation_enabled)
    return null;
  return (
    <Suspense fallback={null}>
      <FeedbackToolbar key={`${user.id}:${pathname}`} />
    </Suspense>
  );
}
