import type { ReactNode } from "react";

export function ScreenState({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="screen-state">
      <img alt="Accumulate" className="state-logo" src="/accumulate-logo.svg" />
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <div className="state-copy">{children}</div>
    </main>
  );
}
