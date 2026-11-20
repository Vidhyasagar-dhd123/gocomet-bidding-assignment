import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { ApiError } from "@/api/client";
import { suppliersQuery, useCreateSupplier } from "@/api/queries";
import type { Supplier } from "@/api/types";
import { DataTable, Field, Notice, PageHeader, Section, Spinner, type Column } from "@/components/ui";
import { aria, applyServerErrors } from "@/lib/forms";
import { fmtDate } from "@/lib/format";
import { useAppStore } from "@/lib/store";

const schema = z.object({
  name: z.string().trim().min(2, "At least 2 characters").max(200),
  contact_email: z.union([z.literal(""), z.string().trim().email("Enter a valid email").max(320)]),
});
type FormValues = z.infer<typeof schema>;

export function Component() {
  const suppliers = useQuery(suppliersQuery());
  const create = useCreateSupplier();
  const acting = useAppStore((s) => s.actingSupplierId);
  const setActing = useAppStore((s) => s.setActingSupplier);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { name: "", contact_email: "" } });

  const onSubmit = handleSubmit(async (v) => {
    setFormError(null);
    try {
      const s = await create.mutateAsync({ name: v.name, contact_email: v.contact_email || null });
      toast.success(`Supplier ${s.name} added`);
      reset();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError("name", { type: "server", message: err.message });
      else setFormError(applyServerErrors(err, setError));
    }
  });

  const columns: Column<Supplier>[] = [
    { header: "Name", cell: (s) => <span className="font-medium text-slate-900">{s.name}</span> },
    { header: "Email", cell: (s) => s.contact_email ?? <span className="text-slate-400">—</span> },
    { header: "Added", cell: (s) => <span className="whitespace-nowrap text-slate-500">{fmtDate(s.created_at)}</span> },
    {
      header: "Bidding as",
      align: "right",
      cell: (s) =>
        s.id === acting ? (
          <span className="text-sm font-medium text-accent">Current</span>
        ) : (
          <button className="text-sm font-medium text-accent hover:text-accent-hover" onClick={() => setActing(s.id)}>
            Bid as this supplier
          </button>
        ),
    },
  ];

  return (
    <>
      <PageHeader title="Suppliers" subtitle="Suppliers who can bid on RFQs. Pick one in the header to bid as them." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="Add supplier">
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            <Field label="Name" htmlFor="name" error={errors.name?.message}>
              <input {...register("name")} className={clsx("input", errors.name && "input-error")} {...aria("name", errors.name?.message)} />
            </Field>
            <Field label="Contact email" htmlFor="contact_email" error={errors.contact_email?.message}>
              <input
                type="email"
                {...register("contact_email")}
                className={clsx("input", errors.contact_email && "input-error")}
                {...aria("contact_email", errors.contact_email?.message)}
              />
            </Field>
            {formError && <Notice tone="error">{formError}</Notice>}
            <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
              {isSubmitting ? "Adding…" : "Add supplier"}
            </button>
          </form>
        </Section>
        <Section title="All suppliers" className="lg:col-span-2">
          {suppliers.isPending ? (
            <Spinner />
          ) : suppliers.isError ? (
            <Notice tone="error">{suppliers.error.message}</Notice>
          ) : (
            <DataTable columns={columns} rows={suppliers.data} rowKey={(s) => s.id} empty="No suppliers yet." />
          )}
        </Section>
      </div>
    </>
  );
}
