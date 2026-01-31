import type { ReactNode } from "react";

const GITHUB_URL = "https://github.com/pico-dot-ai/tickets.md";

function ExternalLink({
  href,
  children
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a className="link" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

function Card({
  title,
  children
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="card">
      <div className="cardTitle">{title}</div>
      <div className="cardBody">{children}</div>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="bg">
      <header className="header">
        <div className="container headerInner">
          <div className="brand">
            <div className="brandMark" aria-hidden="true">
              T
            </div>
            <div className="brandText">
              <div className="brandName">Tickets.md</div>
              <div className="brandTag">Open-source, repo-native ticketing</div>
            </div>
          </div>

          <nav className="nav" aria-label="Primary">
            <a className="navLink" href="#goals">
              Goals
            </a>
            <a className="navLink" href="#how">
              How it works
            </a>
            <a className="navLink" href="#get-involved">
              Collaborate
            </a>
            <a className="cta" href={GITHUB_URL} target="_blank" rel="noreferrer">
              GitHub
            </a>
          </nav>
        </div>
      </header>

      <main className="container main">
        <section className="hero">
          <div className="heroLeft">
            <h1 className="h1">Tickets that work with agents.</h1>
            <p className="lead">
              A simple, flexible ticket format and CLI designed for parallel,
              long-running agentic development—without requiring a hosted service
              or network access.
            </p>

            <div className="heroActions">
              <a className="primaryButton" href={GITHUB_URL} target="_blank" rel="noreferrer">
                View the project on GitHub
              </a>
              <a className="secondaryButton" href="#how">
                See the approach
              </a>
            </div>

            <div className="heroNote">
              Apache-2.0 licensed • Built for humans and tools • Designed to be
              merge-friendly
            </div>
          </div>

          <div className="heroRight" aria-hidden="true">
            <div className="codeCard">
              <div className="codeHeader">
                <div className="dot dotRed" />
                <div className="dot dotYellow" />
                <div className="dot dotGreen" />
                <div className="codeTitle">repo</div>
              </div>
              <pre className="code">
                <code>{`/.tickets/
  <ticket-id>/
    ticket.md
    logs/
      <run>.jsonl`}</code>
              </pre>
              <div className="codeFooter">
                Stable ticket definitions. Append-only run logs.
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="goals">
          <h2 className="h2">Goals</h2>
          <p className="p">
            Tickets.md is intentionally small: a proposed format plus a single
            repo-local interface for automation. The goal is to make collaboration
            between people and agents predictable, auditable, and easy to merge.
          </p>

          <div className="grid">
            <Card title="Simple, readable tickets">
              A Markdown-first definition that stays stable over time, with acceptance
              criteria and verification that agents can follow.
            </Card>
            <Card title="Merge-friendly parallelism">
              Per-run, append-only logs reduce conflicts and make concurrent work across
              branches practical.
            </Card>
            <Card title="Offline-first">
              Works in sandboxes and air‑gapped environments. The repo is the
              source of truth.
            </Card>
            <Card title="A consistent interface">
              A small CLI surface is the integration point for humans, IDE helpers, and
              agent tooling.
            </Card>
            <Card title="Agent-safe execution">
              Encourage explicit acceptance criteria, verification steps, and bounded
              iteration so work converges.
            </Card>
            <Card title="Open and collaborative">
              Designed to be shared, improved, and extended—without requiring a hosted
              service to get value.
            </Card>
          </div>
          <div className="callout mt14">
            <div className="calloutTitle">Non-goals (by design)</div>
            <div className="calloutBody">
              Tickets.md is not trying to be a full project management suite, a required
              replacement for GitHub Issues, or a hosted service. The focus is a durable
              in-repo format and an interface agents can reliably use.
            </div>
          </div>
        </section>

        <section className="section" id="how">
          <h2 className="h2">How it works</h2>
          <div className="twoCol">
            <div>
              <p className="p">
                The system separates a human-readable ticket from a machine-friendly
                audit trail:
              </p>
              <ol className="list">
                <li>
                  <span className="listStrong">Define work</span> in a Markdown ticket
                  with front matter and clear acceptance criteria.
                </li>
                <li>
                  <span className="listStrong">Log runs</span> to append-only JSONL files
                  (one file per run) so parallel work stays mergeable.
                </li>
                <li>
                  <span className="listStrong">Integrate tooling</span> via a small CLI
                  surface—agents, IDEs, and humans speak the same interface.
                </li>
              </ol>
            </div>

            <div className="callout">
              <div className="calloutTitle">A collaborative default</div>
              <div className="calloutBody">
                This project is open source and welcomes contributions—from docs and
                examples to validators and integrations. If you build tooling that
                speaks the Tickets.md format, we want to learn from it.
              </div>
              <div className="calloutLinks">
                <ExternalLink href={GITHUB_URL}>Contribute on GitHub</ExternalLink>
                <span className="sep" aria-hidden="true">
                  ·
                </span>
                <ExternalLink href={`${GITHUB_URL}#readme`}>Read the overview</ExternalLink>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="get-involved">
          <h2 className="h2">Get involved</h2>
          <div className="grid">
            <Card title="Use it in a repo">
              Start with the canonical docs in <ExternalLink href={`${GITHUB_URL}/blob/main/TICKETS.md`}>TICKETS.md</ExternalLink>{" "}
              and the project overview in <ExternalLink href={`${GITHUB_URL}/blob/main/README.md`}>README.md</ExternalLink>.
            </Card>
            <Card title="Improve the spec">
              Propose fields, validation rules, and interoperability patterns that help
              agents collaborate across tools and branches.
            </Card>
            <Card title="Build integrations">
              IDE helpers, lightweight dashboards, CI checks, or agent harness adapters—
              all through the same repo-local interface.
            </Card>
          </div>

          <div className="foot">
            <div className="footLeft">Tickets.md is a community project.</div>
            <div className="footRight">
              <ExternalLink href={GITHUB_URL}>GitHub</ExternalLink>
              <span className="sep" aria-hidden="true">
                ·
              </span>
              <ExternalLink href={`${GITHUB_URL}/blob/main/LICENSE`}>Apache-2.0</ExternalLink>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container footerInner">
          <div className="muted">
            Built to keep tickets simple, durable, and friendly to parallel work.
          </div>
          <div className="muted">
            <ExternalLink href={GITHUB_URL}>pico-dot-ai/tickets.md</ExternalLink>
          </div>
        </div>
      </footer>
    </div>
  );
}
