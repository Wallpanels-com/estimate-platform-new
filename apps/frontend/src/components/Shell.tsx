import { LanguageSwitch, useI18n } from "../lib/i18n";
import { NavLink, Outlet } from "react-router-dom";
import {
  FileText,
  BookOpen,
  WandSparkles,
  Trash2,
  LogOut,
  Users,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { canAccess, firstPage } from "../lib/access";
import { Button } from "./ui";
export function Brand() {
  return (
    <span className="brand" translate="no">
      <img
        className="brand-logo"
        src="/brand/wallpanels-verona-transparent.png"
        alt="WALLPANELS.COM — By VERONA HOME"
        width={2172}
        height={724}
      />
      <small>Estimate Platform</small>
    </span>
  );
}
export default function Shell() {
  const { t } = useI18n();

  const { user, signOut } = useAuth();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("Skip to content")}
      </a>
      <aside className="app-nav">
        <div className="nav-brand">
          <NavLink
            to={firstPage(user)}
            className="brand-link"
            aria-label={t("WallPanels home")}
          >
            <Brand />
          </NavLink>
          <LanguageSwitch />
        </div>
        <nav aria-label={t("Main navigation")}>
          {canAccess(user, "estimates") ? (
            <NavLink to="/" end>
              <FileText size={18} />
              {t("Estimates")}
            </NavLink>
          ) : null}
          {canAccess(user, "quick_estimate") ? (
            <NavLink to="/quick-estimate">
              <WandSparkles size={18} />
              {t("Quick estimate")}
            </NavLink>
          ) : null}
          {canAccess(user, "price_book") ? (
            <NavLink to="/price-book">
              <BookOpen size={18} />
              {t("Price book")}
            </NavLink>
          ) : null}
          {canAccess(user, "users") ? (
            <NavLink to="/users">
              <Users size={18} />
              {t("Team accounts")}
            </NavLink>
          ) : null}
          {canAccess(user, "trash") ? (
            <NavLink to="/trash">
              <Trash2 size={18} />
              {t("Trash")}
            </NavLink>
          ) : null}
        </nav>
        <div className="nav-user">
          <span className="avatar" aria-hidden="true">
            {(user?.name || user?.email || "W").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-zero">
            <strong>{user?.name || t("Your account")}</strong>
            <small>{user?.email}</small>
          </div>
          <Button variant="ghost" aria-label={t("Sign out")} onClick={signOut}>
            <LogOut size={17} />
          </Button>
        </div>
      </aside>
      <main id="main-content" className="main-page">
        <Outlet />
      </main>
    </div>
  );
}
