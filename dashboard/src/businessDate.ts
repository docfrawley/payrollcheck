import { createContext, use } from "react";

// The app's today, as the backend gives it, and whether it is the real date.
export interface BusinessDate {
  business_date: string;
  real_date: boolean;
}

// The business date in force, for the header, and a way to read it again once
// the Settings page has changed it.
export interface BusinessDateState {
  businessDate?: BusinessDate;
  reload: () => void;
}

export const BusinessDateContext = createContext<BusinessDateState>({
  reload: () => undefined,
});

export function useBusinessDate(): BusinessDateState {
  return use(BusinessDateContext);
}
