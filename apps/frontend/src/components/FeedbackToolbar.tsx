import { useState } from "react";
import { Agentation } from "agentation";

export default function FeedbackToolbar() {
  const [session, setSession] = useState<string>();
  return (
    <div data-agentation-session={session}>
      <Agentation
        appName="WallPanels Estimate Platform"
        endpoint="http://localhost:4747"
        onSessionCreated={setSession}
      />
    </div>
  );
}
