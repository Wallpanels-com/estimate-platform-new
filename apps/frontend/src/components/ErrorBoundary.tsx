import { Component, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";
import { Button, ErrorNotice } from "./ui";
function Recovery() {
  const { t } = useI18n();
  return (
    <main className="error-page" role="main">
      <h1>{t("This page could not be opened.")}</h1>
      <ErrorNotice>
        {t(
          "Your saved data has not been removed. Reload the page to try again.",
        )}
      </ErrorNotice>
      <Button onClick={() => window.location.reload()}>
        {t("Reload page")}
      </Button>
    </main>
  );
}
/** Recover from a stale lazy-loaded chunk or unexpected render error without a blank screen. */
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <Recovery /> : this.props.children;
  }
}
