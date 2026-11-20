import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
import { ApiError } from "@/api/client";
import { suppliersQuery, usePlaceBid } from "@/api/queries";
import type { RankedBid } from "@/api/types";
import { Field, Notice } from "@/components/ui";
import { aria, applyServerErrors } from "@/lib/forms";
import { fmtMoney } from "@/lib/format";
import { useAppStore } from "@/lib/store";

const money = z.number({ invalid_type_error: "Enter an amount" }).min(0, "Cannot be negative").multipleOf(0.01, "Max 2 decimals");

const schema = z
  .object({
    supplier_id: z.number({ invalid_type_error: "Select a supplier" }).int().positive("Select a supplier"),
    carrier_name: z.string().trim().min(1, "Required").max(120),
    freight_charges: money,
    origin_charges: money,
    destination_charges: money,
    transit_time_days: z.number({ invalid_type_error: "Enter days" }).int("Whole days").min(1).max(365),
    quote_validity_date: z.string().min(1, "Required"),
    remarks: z.string().max(1000),
  })
  .superRefine((v, ctx) => {
    if (v.freight_charges + v.origin_charges + v.destination_charges <= 0)
      ctx.addIssue({ code: "custom", path: ["freight_charges"], message: "Total must be greater than 0" });
    if (v.quote_validity_date && v.quote_validity_date < dayjs().format("YYYY-MM-DD"))
      ctx.addIssue({ code: "custom", path: ["quote_validity_date"], message: "Cannot be in the past" });
  });

type FormValues = z.infer<typeof schema>;


const blank = undefined as unknown as number;

const empty = (supplierId: number | null, pickupDate: string): FormValues => ({
  supplier_id: supplierId ?? 0,
  carrier_name: "",
  freight_charges: blank,
  origin_charges: 0,
  destination_charges: 0,
  transit_time_days: blank,
  quote_validity_date: dayjs(pickupDate).add(30, "day").format("YYYY-MM-DD"),
  remarks: "",
});


export default function BidForm({ rfqId, ranking, pickupDate }: { rfqId: number; ranking: RankedBid[]; pickupDate: string }) {
  const { data: suppliers = [] } = useQuery(suppliersQuery());
  const acting = useAppStore((s) => s.actingSupplierId);
  const placeBid = usePlaceBid(rfqId);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    setError,
    setValue,
    reset,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: empty(acting, pickupDate), mode: "onTouched" });

  const [supplierId, freight, origin, destination] = useWatch({
    control,
    name: ["supplier_id", "freight_charges", "origin_charges", "destination_charges"],
  });
  const total = [freight, origin, destination].reduce((s, n) => s + (Number.isFinite(n) ? n : 0), 0);
  const own = ranking.find((r) => r.bid.supplier_id === supplierId);
  const leader = ranking[0];
  const notLower = own != null && total > 0 && total >= own.bid.total_amount;

  
  useEffect(() => {
    if (acting) setValue("supplier_id", acting, { shouldValidate: false });
  }, [acting, setValue]);

  
  const ownBidId = own?.bid.id;
  useEffect(() => {
    if (!own) {
      reset({ ...empty(getValues("supplier_id"), pickupDate) });
      return;
    }
    const b = own.bid;
    reset({
      supplier_id: b.supplier_id,
      carrier_name: b.carrier_name,
      freight_charges: blank,
      origin_charges: b.origin_charges,
      destination_charges: b.destination_charges,
      transit_time_days: b.transit_time_days,
      quote_validity_date: b.quote_validity_date,
      remarks: b.remarks ?? "",
    });
    
  }, [supplierId, ownBidId]);

  const onSubmit = handleSubmit(async (v) => {
    setFormError(null);
    if (notLower) return setError("freight_charges", { message: `Total must be below your current ${fmtMoney(own!.bid.total_amount)}` });
    try {
      const res = await placeBid.mutateAsync({ ...v, remarks: v.remarks || null });
      toast.success(`Bid of ${fmtMoney(res.bid.total_amount)} placed. You are ${res.rank_label}.`);
      if (res.auction_extended) toast.warning(`Auction extended to ${dayjs(res.current_close_at).format("HH:mm:ss")}`, { description: res.extension_reason ?? undefined });
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error") setError("freight_charges", { type: "server", message: err.message });
      else setFormError(applyServerErrors(err, setError));
    }
  });

  if (suppliers.length === 0)
    return (
      <Notice>
        No suppliers yet. <Link to="/suppliers">Add a supplier</Link> to start bidding.
      </Notice>
    );

  const input = (name: keyof FormValues) => ({ className: clsx("input", errors[name] && "input-error"), ...aria(`bid-${name}`, errors[name]?.message) });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <Field label="Supplier" htmlFor="bid-supplier_id" error={errors.supplier_id?.message}>
        <select {...register("supplier_id", { valueAsNumber: true })} {...input("supplier_id")}>
          <option value={0}>Select supplier</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </Field>

      {supplierId > 0 && (
        <p className="text-sm text-slate-600">
          {own ? (
            <>
              Your bid: <strong className="num">{fmtMoney(own.bid.total_amount)}</strong> ({own.rank_label}).
            </>
          ) : (
            "No bid yet from this supplier."
          )}{" "}
          {leader && leader.bid.supplier_id !== supplierId && (
            <>
              L1 to beat: <strong className="num text-green-700">{fmtMoney(leader.bid.total_amount)}</strong>
            </>
          )}
        </p>
      )}

      <Field label="Carrier name" htmlFor="bid-carrier_name" error={errors.carrier_name?.message}>
        <input {...register("carrier_name")} {...input("carrier_name")} placeholder="e.g. Maersk" />
      </Field>

      <div className="grid grid-cols-3 gap-3">
        <Field label="Freight" htmlFor="bid-freight_charges" error={errors.freight_charges?.message}>
          <input type="number" step="0.01" min={0} inputMode="decimal" {...register("freight_charges", { valueAsNumber: true })} {...input("freight_charges")} />
        </Field>
        <Field label="Origin" htmlFor="bid-origin_charges" error={errors.origin_charges?.message}>
          <input type="number" step="0.01" min={0} inputMode="decimal" {...register("origin_charges", { valueAsNumber: true })} {...input("origin_charges")} />
        </Field>
        <Field label="Destination" htmlFor="bid-destination_charges" error={errors.destination_charges?.message}>
          <input type="number" step="0.01" min={0} inputMode="decimal" {...register("destination_charges", { valueAsNumber: true })} {...input("destination_charges")} />
        </Field>
      </div>

      <div className="flex items-baseline justify-between border-y border-slate-100 py-2 text-sm">
        <span className="text-slate-600">Total</span>
        <span className={clsx("num text-lg font-semibold", notLower ? "text-red-700" : "text-slate-900")}>{fmtMoney(total)}</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Transit (days)" htmlFor="bid-transit_time_days" error={errors.transit_time_days?.message}>
          <input type="number" min={1} max={365} {...register("transit_time_days", { valueAsNumber: true })} {...input("transit_time_days")} />
        </Field>
        <Field label="Quote valid until" htmlFor="bid-quote_validity_date" error={errors.quote_validity_date?.message}>
          <input type="date" {...register("quote_validity_date")} {...input("quote_validity_date")} />
        </Field>
      </div>

      <Field label="Remarks" htmlFor="bid-remarks" error={errors.remarks?.message}>
        <textarea rows={2} {...register("remarks")} {...input("remarks")} />
      </Field>

      {formError && <Notice tone="error">{formError}</Notice>}
      <button type="submit" className="btn-primary w-full" disabled={isSubmitting || notLower}>
        {isSubmitting ? "Submitting…" : own ? "Lower my bid" : "Submit bid"}
      </button>
    </form>
  );
}
