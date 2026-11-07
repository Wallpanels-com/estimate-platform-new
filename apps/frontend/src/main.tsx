import React, { Suspense, lazy, useEffect } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  useLocation,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./lib/auth";
import { ApiError } from "./lib/api";
import { Loading, NoticeProvider } from "./components/ui";
import Shell from "./components/Shell";
import { PageGate, NoPageAccess } from "./components/PageGate";
import ErrorBoundary from "./components/ErrorBoundary";
import Auth from "./pages/Auth";
import StaffFeedback from "./components/StaffFeedback";
import Estimates from "./pages/Estimates";
import "@fontsource-variable/montserrat";
import "./styles.css";
import { LanguageProvider } from "./lib/i18n";
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Builder = lazy(() => import("./pages/Builder"));
const PriceBook = lazy(() => import("./pages/PriceBook"));
const QuickEstimate = lazy(() => import("./pages/QuickEstimate"));
const Staff = lazy(() => import("./pages/Staff"));
const HR = lazy(() => import("./pages/HR"));
const Users = lazy(() => import("./pages/Users"));
const client = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (attempt, error) =>
        !(error instanceof ApiError && error.status < 500) && attempt < 1,
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
});
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
function Protected() {
  const { token, loading } = useAuth();
  return !token ? (
    <Navigate to="/login" replace />
  ) : loading ? (
    <Loading />
  ) : (
    <Outlet />
  );
}
function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/register" element={<Auth register />} />
        <Route element={<Protected />}>
          <Route element={<Shell />}>
            <Route
              index
              element={
                <PageGate page="estimates">
                  <Estimates />
                </PageGate>
              }
            />
            <Route path="access" element={<NoPageAccess />} />
            <Route
              path="hr"
              element={
                <PageGate page="hr">
                  <HR />
                </PageGate>
              }
            />
            <Route
              path="hr/staff"
              element={
                <PageGate page="hr">
                  <Staff />
                </PageGate>
              }
            />
            <Route
              path="onboarding"
              element={
                <Suspense fallback={<Loading />}>
                  <Onboarding />
                </Suspense>
              }
            />
            <Route
              path="trash"
              element={
                <PageGate page="trash">
                  <Estimates trash />
                </PageGate>
              }
            />
            <Route
              path="price-book"
              element={
                <Suspense fallback={<Loading />}>
                  <PageGate page="price_book">
                    <PriceBook />
                  </PageGate>
                </Suspense>
              }
            />
            <Route
              path="users"
              element={
                <Suspense fallback={<Loading />}>
                  <PageGate page="users">
                    <Users />
                  </PageGate>
                </Suspense>
              }
            />
            <Route
              path="pricing-config"
              element={<Navigate to="/price-book" replace />}
            />
            <Route
              path="quick-estimate"
              element={
                <Suspense fallback={<Loading />}>
                  <PageGate page="quick_estimate">
                    <QuickEstimate />
                  </PageGate>
                </Suspense>
              }
            />
          </Route>
          <Route path="estimates/:id" element={<Builder />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <QueryClientProvider client={client}>
        <NoticeProvider>
          <BrowserRouter>
            <AuthProvider>
              <ScrollToTop />
              <ErrorBoundary>
                <App />
              </ErrorBoundary>
              <StaffFeedback />
            </AuthProvider>
          </BrowserRouter>
        </NoticeProvider>
      </QueryClientProvider>
    </LanguageProvider>
  </React.StrictMode>,
);
