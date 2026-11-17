import { type ReactNode, useMemo } from "react";
import { Navigate, useLocation } from "react-router";
import { api } from "../api";
import { BusinessDateContext } from "../businessDate";
import { ReviewerContext, type SignInState, useSignedIn } from "../reviewer";
import { SIGN_IN } from "../paths";
import { useLoad } from "../useLoad";
import { PageFrame } from "./PageFrame";
import { StateMessage } from "./StateMessage";
import { SignOutButton } from "./SignOutButton";

// Keeps a page to signed-in reviewers. A visitor goes to the sign-in page,
// which brings them back here once they have signed in.
export function RequireReviewer({
  children,
}: Readonly<{ children: ReactNode }>) {
  const signedIn = useSignedIn();
  const location = useLocation();
  if (signedIn === undefined) return null;
  if (!signedIn) {
    const state: SignInState = { from: location };
    return <Navigate to={SIGN_IN} state={state} replace />;
  }
  return <ReviewerProvider>{children}</ReviewerProvider>;
}

// Loads the reviewer signed in for the pages, or says why it can't, and the
// business date for the header.
function ReviewerProvider({ children }: Readonly<{ children: ReactNode }>) {
  const { data: reviewer, error } = useLoad(api.getSignedInReviewer);
  const { data: businessDate, reload } = useLoad(api.getBusinessDate);
  const dated = useMemo(
    () => ({ businessDate, reload }),
    [businessDate, reload],
  );
  if (!reviewer)
    return (
      <PageFrame>
        <StateMessage error={error} />
        {error && <SignOutButton className="button" />}
      </PageFrame>
    );
  return (
    <ReviewerContext value={reviewer}>
      <BusinessDateContext value={dated}>{children}</BusinessDateContext>
    </ReviewerContext>
  );
}
