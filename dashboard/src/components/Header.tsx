import { use } from "react";
import { Link, NavLink, useMatch } from "react-router";
import { ReviewerContext } from "../reviewer";
import {
  CASE_PAGE,
  CONFIGURATION,
  IMPROVEMENT,
  QUEUE,
  SCOREBOARD,
} from "../paths";
import { AccountMenu } from "./AccountMenu";
import { Brand } from "./Brand";

// The band across the top of every signed-in page: the brand, the main nav,
// and the reviewer signed in with their menu once they have loaded.
export function Header() {
  const reviewer = use(ReviewerContext);
  // A case's page belongs to the queue.
  const queuePage = useMatch(QUEUE);
  const casePage = useMatch(CASE_PAGE);
  const onQueue = queuePage !== null || casePage !== null;
  return (
    <header className="header">
      <div className="header-bar">
        <Link to={QUEUE} className="brand">
          <Brand />
        </Link>
        <nav className="nav" aria-label="Main">
          <Link
            to={QUEUE}
            className={onQueue ? "active" : undefined}
            aria-current={onQueue ? "page" : undefined}
          >
            Queue
          </Link>
          <NavLink to={SCOREBOARD}>Scoreboard</NavLink>
          <NavLink to={IMPROVEMENT}>Improvement</NavLink>
          <NavLink to={CONFIGURATION}>Configuration</NavLink>
        </nav>
        {reviewer && (
          <div className="who" role="group" aria-label="Signed in">
            <p className="who-text">
              <span className="who-name">{reviewer.name}</span>
              <span className="who-role">{reviewer.role}</span>
            </p>
            <AccountMenu />
          </div>
        )}
      </div>
    </header>
  );
}
