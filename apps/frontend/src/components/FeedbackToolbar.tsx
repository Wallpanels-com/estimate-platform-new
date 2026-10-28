import { useState } from "react";
import { useFeedbackOverlay } from "../lib/feedbackOverlay";
import { Agentation } from "agentation";

export default function FeedbackToolbar() {
  const portalContainer = useFeedbackOverlay();
  const [session, setSession] = useState<string>();
  return (
    <div data-agentation-session={session}>
      <Agentation
        portalContainer={portalContainer}
        appName="WallPanels Estimate Platform"
        endpoint="http://localhost:4747"
        onSessionCreated={setSession}
      />
    </div>
  );
}
