import { useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { post } from "../lib/api";
import {
  embeddedModule,
  isEmbedded,
  notifyPortal,
  portalOrigin,
} from "../lib/portal";
import { Loading, ErrorNotice } from "./ui";

export default function PortalEmbed({ children }: { children: ReactNode }) {
  const { token, signIn, loading, user } = useAuth();
  const { setLanguage, t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!isEmbedded) return;
    let connecting = false;
    const receive = async (event: MessageEvent) => {
      if (event.origin !== portalOrigin || event.source !== window.parent)
        return;
      if (
        event.data?.type === "wp:language" &&
        ["ru", "en"].includes(event.data.language)
      )
        setLanguage(event.data.language);
      if (event.data?.type !== "wp:sign-in" || connecting || token) return;
      connecting = true;
      try {
        const result = await post<{ access_token: string }>(
          "/auth/portal-exchange",
          { code: event.data.code },
        );
        signIn(result.access_token);
        navigate(embeddedModule === "hr" ? "/hr/staff?view=chart" : "/", { replace: true });
      } catch {
        setError(true);
        notifyPortal({ type: "wp:error" });
      } finally {
        connecting = false;
      }
    };
    window.addEventListener("message", receive);
    if (!token) notifyPortal({ type: "wp:ready" });
    return () => window.removeEventListener("message", receive);
  }, [token, setLanguage]);
  useEffect(() => {
    if (!isEmbedded || !user || loading) return;
    notifyPortal({ type: "wp:connected" });
  }, [user, loading, location.pathname]);
  if (isEmbedded && (!token || loading || !user))
    return error ? (
      <ErrorNotice>
        {t("Could not open the workspace. Please try again.")}
      </ErrorNotice>
    ) : (
      <Loading />
    );
  return children;
}
