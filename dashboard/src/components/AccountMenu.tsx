import { ChevronDown, Palette, Settings } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { NavLink } from "react-router";
import { initials } from "../format";
import { ROLE_TITLES, isComplianceManager, useReviewer } from "../reviewer";
import { SETTINGS } from "../paths";
import { SignOutButton } from "./SignOutButton";

// The signed-in reviewer's avatar, which opens a menu with who they are, the
// Settings page (Appearance, for a reviewer, who sees only that of it) and Sign
// out. A click outside, focus moving away or Escape closes it.
export function AccountMenu() {
  const reviewer = useReviewer();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const account = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeOutside(event: PointerEvent) {
      if (
        event.target instanceof Node &&
        account.current?.contains(event.target)
      )
        return;
      setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    }
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div
      className="account"
      ref={account}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={button}
        type="button"
        className="avatar-button"
        aria-label="Account"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <span className="avatar">{initials(reviewer.name)}</span>
        <ChevronDown />
      </button>
      {open && (
        // Focusable, so a click on its text keeps focus, and the menu, open.
        <div id={menuId} className="account-menu" tabIndex={-1}>
          <p className="account-who">
            <span className="who-name">{reviewer.name}</span>
            <span className="small">{ROLE_TITLES[reviewer.role]}</span>
            <span className="muted small">{reviewer.email}</span>
          </p>
          <NavLink
            to={SETTINGS}
            className="menu-item"
            onClick={() => {
              setOpen(false);
            }}
          >
            {isComplianceManager(reviewer) ? (
              <>
                <Settings />
                Settings
              </>
            ) : (
              <>
                <Palette />
                Appearance
              </>
            )}
          </NavLink>
          <SignOutButton className="menu-item" />
        </div>
      )}
    </div>
  );
}
