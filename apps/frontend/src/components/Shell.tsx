import { useState } from "react";
import { LanguageSwitch, useI18n } from "../lib/i18n";
import { NavLink, Outlet } from "react-router-dom";
import {
  FileText,
  BookOpen,
  WandSparkles,
  Trash2,
  LogOut,
  Users,
  BriefcaseBusiness,
  PanelLeftClose,
  PanelLeftOpen,
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
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("wallpanels.nav-collapsed") === "true";
    } catch {
      return false;
    }
  });
  const toggleNavigation = () => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem("wallpanels.nav-collapsed", String(next));
      } catch {
        // Navigation still works when browser storage is unavailable.
      }
      return next;
    });
  };
  return (
    <div className={`app-shell${collapsed ? " nav-collapsed" : ""}`}>
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
            {collapsed ? (
              <img
                className="nav-brand-mark"
                src="/favicon.svg"
                alt="WallPanels"
                width={40}
                height={40}
              />
            ) : (
              <Brand />
            )}
          </NavLink>
          <div className="nav-tools">
            <LanguageSwitch />
            <button
              type="button"
              className="nav-toggle"
              aria-label={t(collapsed ? "Expand menu" : "Collapse menu")}
              title={t(collapsed ? "Expand menu" : "Collapse menu")}
              aria-expanded={!collapsed}
              aria-controls="main-navigation"
              onClick={toggleNavigation}
            >
              {collapsed ? (
                <PanelLeftOpen size={18} />
              ) : (
                <PanelLeftClose size={18} />
              )}
            </button>
          </div>
        </div>
        <nav id="main-navigation" aria-label={t("Main navigation")}>
          {canAccess(user, "estimates") ? (
            <NavLink
              aria-label={t("Estimates")}
              title={collapsed ? t("Estimates") : undefined}
              to="/"
              end
            >
              <FileText size={18} />
              <span className="nav-label">{t("Estimates")}</span>
            </NavLink>
          ) : null}
          {canAccess(user, "quick_estimate") ? (
            <NavLink
              aria-label={t("Quick estimate")}
              title={collapsed ? t("Quick estimate") : undefined}
              to="/quick-estimate"
            >
              <WandSparkles size={18} />
              <span className="nav-label">{t("Quick estimate")}</span>
            </NavLink>
          ) : null}
          {canAccess(user, "price_book") ? (
            <NavLink
              aria-label={t("Price book")}
              title={collapsed ? t("Price book") : undefined}
              to="/price-book"
            >
              <BookOpen size={18} />
              <span className="nav-label">{t("Price book")}</span>
            </NavLink>
          ) : null}
          {canAccess(user, "hr") ? (
            <NavLink
              aria-label={t("HR department")}
              title={collapsed ? t("HR department") : undefined}
              to="/hr"
            >
              <BriefcaseBusiness size={18} />
              <span className="nav-label">{t("HR department")}</span>
            </NavLink>
          ) : null}
          {canAccess(user, "users") ? (
            <NavLink
              aria-label={t("Access")}
              title={collapsed ? t("Access") : undefined}
              to="/users"
            >
              <Users size={18} />
              <span className="nav-label">{t("Access")}</span>
            </NavLink>
          ) : null}
          {canAccess(user, "trash") ? (
            <NavLink
              aria-label={t("Trash")}
              title={collapsed ? t("Trash") : undefined}
              to="/trash"
            >
              <Trash2 size={18} />
              <span className="nav-label">{t("Trash")}</span>
            </NavLink>
          ) : null}
        </nav>
        <div className="nav-user">
          <span className="avatar" aria-hidden="true">
            {(user?.name || user?.email || "W").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-zero nav-user-details">
            <strong>{user?.name || t("Your account")}</strong>
            <small>{user?.email}</small>
          </div>
          <Button
            variant="ghost"
            aria-label={t("Sign out")}
            title={collapsed ? t("Sign out") : undefined}
            onClick={signOut}
          >
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
