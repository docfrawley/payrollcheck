import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { api } from "../api";
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

// Loads the reviewer signed in for the pages, or says why it can't.
function ReviewerProvider({ children }: Readonly<{ children: ReactNode }>) {
  const { data: reviewer, error } = useLoad(api.getSignedInReviewer);
  if (!reviewer)
    return (
      <PageFrame>
        <StateMessage error={error} />
        {error && <SignOutButton className="button" />}
      </PageFrame>
    );
  return <ReviewerContext value={reviewer}>{children}</ReviewerContext>;
}
