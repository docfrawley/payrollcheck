import { use } from "react";
import { Link, NavLink, useMatch } from "react-router";
import { useBusinessDate } from "../businessDate";
import { date } from "../format";
import { ReviewerContext, ROLE_TITLES, isComplianceManager } from "../reviewer";
import {
  CASE_PAGE,
  CONFIGURATION,
  IMPROVEMENT,
  PROJECTS,
  QUEUE,
  SCOREBOARD,
} from "../paths";
import { AccountMenu } from "./AccountMenu";
import { Brand } from "./Brand";
import { SyntheticData } from "./SyntheticData";

// The band across the top of every signed-in page: the brand, the chip saying
// the data is synthetic beside the business date, the main nav, and the
// reviewer signed in with their menu once they have loaded. Improvement is in
// the nav for the compliance manager alone.
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
        <div className="band-notes">
          <SyntheticData />
          <BusinessDateNote />
        </div>
        <nav className="nav" aria-label="Main">
          <Link
            to={QUEUE}
            className={onQueue ? "active" : undefined}
            aria-current={onQueue ? "page" : undefined}
          >
            Queue
          </Link>
          <NavLink to={PROJECTS}>Projects</NavLink>
          <NavLink to={SCOREBOARD}>Scoreboard</NavLink>
          {reviewer && isComplianceManager(reviewer) && (
            <NavLink to={IMPROVEMENT}>Improvement</NavLink>
          )}
          <NavLink to={CONFIGURATION}>Configuration</NavLink>
        </nav>
        {reviewer && (
          <div className="who" role="group" aria-label="Signed in">
            <p className="who-text">
              <span className="who-name">{reviewer.name}</span>
              <span className="who-role">{ROLE_TITLES[reviewer.role]}</span>
            </p>
            <AccountMenu />
          </div>
        )}
      </div>
    </header>
  );
}

// The app's today, once it has loaded.
function BusinessDateNote() {
  const { businessDate } = useBusinessDate();
  if (!businessDate) return null;
  return (
    <p className="business-date">
      Business date{" "}
      <span className="mono">{date(businessDate.business_date)}</span>
    </p>
  );
}
