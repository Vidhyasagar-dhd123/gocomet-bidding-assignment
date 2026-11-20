import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { ApiError, DEFAULT_VALIDATION_MESSAGE } from "@/api/client";

/**
 * Puts server-side field errors on their inputs and returns the message that
 * belongs to the whole form (or null when every error was attached to a field).
 */
export function applyServerErrors<T extends FieldValues>(err: unknown, setError: UseFormSetError<T>): string | null {
  if (!(err instanceof ApiError)) return "Something went wrong";
  const fields = Object.entries(err.fieldErrors);
  fields.forEach(([field, message]) => setError(field as Path<T>, { type: "server", message }));
  return fields.length > 0 && err.message === DEFAULT_VALIDATION_MESSAGE ? null : err.message;
}

/** aria wiring for an input rendered inside <Field>. */
export const aria = (id: string, error?: string) => ({
  id,
  "aria-invalid": error ? true : undefined,
  "aria-describedby": error ? `${id}-error` : undefined,
});
