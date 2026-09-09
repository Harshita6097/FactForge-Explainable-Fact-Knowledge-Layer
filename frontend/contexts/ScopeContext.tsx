"use client";

import { createContext, useContext, useState, ReactNode } from "react";

export interface Scope {
  projectId: string | null;
  projectName: string | null;
  documentId: string | null;
  documentName: string | null;
}

interface ScopeContextValue {
  scope: Scope;
  setProject: (id: string, name: string) => void;
  setDocument: (id: string, name: string) => void;
  clearDocument: () => void;
  clearProject: () => void;
  scopeLabel: string;
}

const ScopeContext = createContext<ScopeContextValue | null>(null);

const EMPTY: Scope = { projectId: null, projectName: null, documentId: null, documentName: null };

export function ScopeProvider({ children }: { children: ReactNode }) {
  const [scope, setScope] = useState<Scope>(EMPTY);

  const setProject = (id: string, name: string) =>
    setScope({ projectId: id, projectName: name, documentId: null, documentName: null });

  const setDocument = (id: string, name: string) =>
    setScope((s) => ({ ...s, documentId: id, documentName: name }));

  const clearDocument = () =>
    setScope((s) => ({ ...s, documentId: null, documentName: null }));

  const clearProject = () => setScope(EMPTY);

  const scopeLabel = scope.documentName ?? scope.projectName ?? "All projects";

  return (
    <ScopeContext.Provider value={{ scope, setProject, setDocument, clearDocument, clearProject, scopeLabel }}>
      {children}
    </ScopeContext.Provider>
  );
}

export function useScope() {
  const ctx = useContext(ScopeContext);
  if (!ctx) throw new Error("useScope must be used inside ScopeProvider");
  return ctx;
}
