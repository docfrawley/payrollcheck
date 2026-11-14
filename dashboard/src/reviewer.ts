import { createContext, use, useEffect, useState } from "react";
import type { Location } from "react-router";
import type { Reviewer } from "./api";
import { followSession } from "./auth";

// The reviewer signed in, which RequireReviewer provides to the pages it guards.
export const ReviewerContext = createContext<Reviewer | undefined>(undefined);

// Where the sign-in page sends a reviewer once they have signed in.
export interface SignInState {
  from?: Location;
}

// The reviewer signed in, for the pages inside RequireReviewer.
export function useReviewer(): Reviewer {
  const reviewer = use(ReviewerContext);
  if (!reviewer) throw new Error("This page needs a signed-in reviewer");
  return reviewer;
}

// Whether a reviewer is signed in, or undefined until Supabase has said.
export function useSignedIn(): boolean | undefined {
  const [signedIn, setSignedIn] = useState<boolean>();
  useEffect(() => followSession(setSignedIn), []);
  return signedIn;
}
