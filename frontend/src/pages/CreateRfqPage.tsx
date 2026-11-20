import { zodResolver } from "@hookform/resolvers/zod";
import clsx from "clsx";
import dayjs from "dayjs";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateRfq } from "@/api/queries";
import type { ExtensionTrigger } from "@/api/types";
import { Field, Notice, PageHeader, Section } from "@/components/ui";
import { aria, applyServerErrors } from "@/lib/forms";
import { localToIso, toLocalInput, TRIGGER_HELP, TRIGGER_LABEL } from "@/lib/format";

const TRIGGERS = Object.keys(TRIGGER_LABEL) as ExtensionTrigger[];
const minutes = z.number({ invalid_type_error: "Enter a number" }).int("Whole minutes only").min(1, "At least 1").max(1440, "At most 1440");


const schema = z
  .object({
    name: z.string().trim().min(3, "At least 3 characters").max(200),
    reference_id: z
      .string()
      .trim()
      .max(64)
      .refine((v) => v === "" || /^[A-Za-z0-9][A-Za-z0-9_\-/]{2,}$/.test(v), "3–64 letters, digits, - _ /"),
    description: z.string().max(5000),
    pickup_date: z.string().min(1, "Required"),
    bid_start_at: z.string().min(1, "Required"),
    bid_close_at: z.string().min(1, "Required"),
    forced_close_at: z.string().min(1, "Required"),
    trigger_window_minutes: minutes,
    extension_minutes: minutes,
    extension_trigger: z.enum(["BID_RECEIVED", "ANY_RANK_CHANGE", "L1_RANK_CHANGE"]),
  })
  .superRefine((v, ctx) => {
    const start = Date.parse(v.bid_start_at);
    const close = Date.parse(v.bid_close_at);
    const forced = Date.parse(v.forced_close_at);
    const issue = (path: string, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
    if (close <= start) issue("bid_close_at", "Must be after bid start");
    else if (close <= Date.now()) issue("bid_close_at", "Must be in the future");
    if (forced <= close) issue("forced_close_at", "Must be later than bid close");
    if (v.pickup_date && v.bid_start_at && v.pickup_date < v.bid_start_at.slice(0, 10)) issue("pickup_date", "Cannot be before bid start date");
  });

type FormValues = z.infer<typeof schema>;

function defaults(): FormValues {
  const start = dayjs().add(5, "minute").startOf("minute");
  return {
    name: "",
    reference_id: "",
    description: "",
    pickup_date: start.add(7, "day").format("YYYY-MM-DD"),
    bid_start_at: toLocalInput(start.toDate()),
    bid_close_at: toLocalInput(start.add(1, "hour").toDate()),
    forced_close_at: toLocalInput(start.add(90, "minute").toDate()),
    trigger_window_minutes: 10,
    extension_minutes: 5,
    extension_trigger: "BID_RECEIVED",
  };
}

export function Component() {
  const navigate = useNavigate();
  const create = useCreateRfq();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: defaults(), mode: "onTouched" });

  const onSubmit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      const rfq = await create.mutateAsync({
        ...v,
        reference_id: v.reference_id || null,
        description: v.description || null,
        bid_start_at: localToIso(v.bid_start_at),
        bid_close_at: localToIso(v.bid_close_at),
        forced_close_at: localToIso(v.forced_close_at),
      });
      toast.success(`RFQ ${rfq.reference_id} created`);
      navigate(`/auctions/${rfq.id}`);
    } catch (err) {
      const msg = applyServerErrors(err, setError);
      if (msg?.includes("reference")) setError("reference_id", { type: "server", message: msg });
      else setFormError(msg);
    }
  });

  const input = (name: keyof FormValues) => ({ className: clsx("input", errors[name] && "input-error"), ...aria(name, errors[name]?.message) });

  return (
    <>
      <PageHeader title="New RFQ" subtitle="Create an RFQ with British auction bidding." />
      <form onSubmit={onSubmit} noValidate className="grid gap-6 lg:grid-cols-5">
        <Section title="RFQ details" className="lg:col-span-3">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="RFQ name" htmlFor="name" error={errors.name?.message}>
                <input {...register("name")} {...input("name")} placeholder="e.g. Mumbai to Rotterdam FCL" />
              </Field>
            </div>
            <Field label="Reference ID" htmlFor="reference_id" error={errors.reference_id?.message} hint="Leave empty to auto-generate">
              <input {...register("reference_id")} {...input("reference_id")} placeholder="RFQ-1001" />
            </Field>
            <Field label="Pickup / service date" htmlFor="pickup_date" error={errors.pickup_date?.message}>
              <input type="date" {...register("pickup_date")} {...input("pickup_date")} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Description" htmlFor="description" error={errors.description?.message}>
                <textarea rows={3} {...register("description")} {...input("description")} placeholder="Cargo, volumes, special requirements" />
              </Field>
            </div>
            <Field label="Bid start" htmlFor="bid_start_at" error={errors.bid_start_at?.message}>
              <input type="datetime-local" {...register("bid_start_at")} {...input("bid_start_at")} />
            </Field>
            <Field label="Bid close" htmlFor="bid_close_at" error={errors.bid_close_at?.message}>
              <input type="datetime-local" {...register("bid_close_at")} {...input("bid_close_at")} />
            </Field>
            <Field label="Forced bid close" htmlFor="forced_close_at" error={errors.forced_close_at?.message} hint="Hard stop; extensions never go past it">
              <input type="datetime-local" {...register("forced_close_at")} {...input("forced_close_at")} />
            </Field>
          </div>
        </Section>

        <div className="flex flex-col gap-6 lg:col-span-2">
          <Section title="Auction configuration">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Trigger window (X min)" htmlFor="trigger_window_minutes" error={errors.trigger_window_minutes?.message}>
                <input type="number" min={1} max={1440} {...register("trigger_window_minutes", { valueAsNumber: true })} {...input("trigger_window_minutes")} />
              </Field>
              <Field label="Extension (Y min)" htmlFor="extension_minutes" error={errors.extension_minutes?.message}>
                <input type="number" min={1} max={1440} {...register("extension_minutes", { valueAsNumber: true })} {...input("extension_minutes")} />
              </Field>
            </div>
            <fieldset className="mt-4">
              <legend className="label">Extension trigger</legend>
              <div className="space-y-2">
                {TRIGGERS.map((t) => (
                  <label key={t} className="flex cursor-pointer gap-3 rounded-md border border-slate-200 p-3 has-checked:border-accent has-checked:bg-blue-50">
                    <input type="radio" value={t} {...register("extension_trigger")} className="mt-0.5 text-accent focus:ring-accent" />
                    <span className="text-sm">
                      <span className="font-medium text-slate-900">{TRIGGER_LABEL[t]}</span>
                      <span className="block text-slate-500">{TRIGGER_HELP[t]}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </Section>
          <Preview control={control} />
        </div>

        <div className="flex flex-col gap-3 lg:col-span-5">
          {formError && <Notice tone="error">{formError}</Notice>}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Creating…" : "Create RFQ"}
            </button>
          </div>
        </div>
      </form>
    </>
  );
}


function Preview({ control }: { control: ReturnType<typeof useForm<FormValues>>["control"] }) {
  const [start, close, forced, x, y] = useWatch({ control, name: ["bid_start_at", "bid_close_at", "forced_close_at", "trigger_window_minutes", "extension_minutes"] });
  const consistent = Date.parse(start) < Date.parse(close) && Date.parse(close) < Date.parse(forced);
  if (!consistent || !x || !y || Number.isNaN(x) || Number.isNaN(y)) return null;
  const f = (v: string) => dayjs(v).format("DD MMM HH:mm");
  return (
    <Notice>
      Bidding runs <strong>{f(start)}</strong> → <strong>{f(close)}</strong>. Activity after{" "}
      <strong>{dayjs(close).subtract(x, "minute").format("HH:mm")}</strong> can extend it by {y} min at a time, never beyond{" "}
      <strong>{f(forced)}</strong>.
    </Notice>
  );
}
