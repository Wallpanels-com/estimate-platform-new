import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { canAccess, firstPage, type PageKey } from "../lib/access";
import { useI18n } from "../lib/i18n";

export function PageGate({
  page,
  children,
}: {
  page: PageKey;
  children: ReactNode;
}) {
  const { user } = useAuth();
  return canAccess(user, page) ? (
    children
  ) : (
    <Navigate to={firstPage(user)} replace />
  );
}
export function NoPageAccess() {
  const { user } = useAuth();
  const { t } = useI18n();
  const target = firstPage(user);
  if (target !== "/access") return <Navigate to={target} replace />;
  return (
    <section className="empty-state">
      <h1>{t("No pages assigned yet")}</h1>
      <p>{t("Contact Dmitry to request access. Your account is active.")}</p>
    </section>
  );
}
