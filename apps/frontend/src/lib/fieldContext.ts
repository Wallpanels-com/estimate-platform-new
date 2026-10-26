import { createContext } from "react";

export const FieldContext = createContext<{
  id: string;
  labelId: string;
  hintId?: string;
} | null>(null);
