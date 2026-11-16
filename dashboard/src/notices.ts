// The shapes of a case's send-back notice and what the outbox sent, as the
// backend gives them.

// A submission's send-back notice: the agent's draft, if it wrote one, and the
// reviewer's edit, both kept.
export interface Notice {
  submission_no: number;
  draft: string | null;
  drafted_by: string | null;
  drafted_at: string | null;
  edited_text: string | null;
  edited_by: string | null;
  edited_at: string | null;
  sent_by: string | null;
  sent_at: string | null;
}

// A notice sent to the subcontractor, as the outbox recorded it.
export interface OutboxRecord {
  outbox_id: number;
  submission_no: number;
  to_address: string;
  subject: string;
  body: string;
  sent_by: string;
  sent_at: string;
  draft: string | null;
}
