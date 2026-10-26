import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request, TOKEN_KEY } from "./api";
import type { User } from "./types";
const Context = createContext<{
  token: string | null;
  user?: User;
  loading: boolean;
  signIn: (token: string) => void;
  signOut: () => void;
}>({ token: null, loading: false, signIn: () => {}, signOut: () => {} });
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const client = useQueryClient();
  const me = useQuery({
    queryKey: ["me", token],
    queryFn: () => request<User>("/auth/me"),
    enabled: !!token,
    retry: false,
  });
  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    client.clear();
  }
  useEffect(() => {
    const expire = () => signOut();
    window.addEventListener("wallpanels:unauthorized", expire);
    return () => window.removeEventListener("wallpanels:unauthorized", expire);
  }, [client]);
  return (
    <Context.Provider
      value={{
        token,
        user: me.data,
        loading: !!token && me.isLoading,
        signIn: (value) => {
          localStorage.setItem(TOKEN_KEY, value);
          setToken(value);
        },
        signOut,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export const useAuth = () => useContext(Context);
