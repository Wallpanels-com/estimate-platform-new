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
import ErrorBoundary from "./components/ErrorBoundary";
import Auth from "./pages/Auth";
import StaffFeedback from "./components/StaffFeedback";
import Estimates from "./pages/Estimates";
import "./styles.css";
import { LanguageProvider } from "./lib/i18n";
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Builder = lazy(() => import("./pages/Builder"));
const PriceBook = lazy(() => import("./pages/PriceBook"));
const QuickEstimate = lazy(() => import("./pages/QuickEstimate"));
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
            <Route index element={<Estimates />} />
            <Route
              path="onboarding"
              element={
                <Suspense fallback={<Loading />}>
                  <Onboarding />
                </Suspense>
              }
            />
            <Route path="trash" element={<Estimates trash />} />
            <Route
              path="price-book"
              element={
                <Suspense fallback={<Loading />}>
                  <PriceBook />
                </Suspense>
              }
            />
            <Route
              path="users"
              element={
                <Suspense fallback={<Loading />}>
                  <Users />
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
                  <QuickEstimate />
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
