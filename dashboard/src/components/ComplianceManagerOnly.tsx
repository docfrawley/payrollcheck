import type { ReactNode } from "react";
import { isComplianceManager, useReviewer } from "../reviewer";
import { NotAllowed } from "./NotAllowed";
import { PageHeader } from "./PageHeader";

// A page only the compliance manager may open. Anyone else gets the title they
// see, what they can't do, and what of the page is theirs, if anything.
export function ComplianceManagerOnly({
  title,
  action,
  forOthers,
  children,
}: Readonly<{
  title: string;
  action: string;
  forOthers?: ReactNode;
  children: ReactNode;
}>) {
  const reviewer = useReviewer();
  if (isComplianceManager(reviewer)) return <>{children}</>;
  return (
    <>
      <PageHeader title={title} />
      <div className="column">
        <NotAllowed action={action} />
        {forOthers}
      </div>
    </>
  );
}
