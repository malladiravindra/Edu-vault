"use client";

import type { ReactNode } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import type { AccessModel, CourseInput } from "@/types";
import { COURSE_STATUS, toOptions } from "@/lib/constants";
import { formatAccessDuration } from "@/lib/format";
import { useCourseCategories } from "@/hooks/use-courses";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  DURATION_PRESETS,
  EMPTY_COURSE_VALUES,
  LIFETIME,
  SHORT_DESCRIPTION_MAX,
  courseSchema,
  formValuesToInput,
  type CourseFormValues,
} from "./course-schema";

const ACCESS_MODEL_OPTIONS: { value: AccessModel; title: string; help: string }[] = [
  { value: "free", title: "Free", help: "Students get instant access as soon as they register." },
  { value: "paid", title: "Paid", help: "Students get access after completing payment." },
  { value: "approval", title: "Approval required", help: "An admin reviews and approves each registration." },
];

const STATUS_OPTIONS = toOptions(COURSE_STATUS);

function durationItems(current: string) {
  const items = [
    ...DURATION_PRESETS.map((d) => ({ value: String(d), label: `${d} days` })),
    { value: LIFETIME, label: "Lifetime access" },
  ];
  if (current && !items.some((i) => i.value === current)) {
    items.unshift({ value: current, label: formatAccessDuration(Number(current)) });
  }
  return items;
}

interface CourseFormProps {
  defaultValues?: CourseFormValues;
  mode: "create" | "edit";
  isPending?: boolean;
  /** Resolve `true` when saved so edit mode can mark the form as pristine. */
  onSubmit: (input: CourseInput) => Promise<boolean>;
  onCancel?: () => void;
  /** Optional live side panel (rendered to the right on large screens). */
  renderAside?: (values: CourseFormValues) => ReactNode;
}

export function CourseForm({ defaultValues, mode, isPending, onSubmit, onCancel, renderAside }: CourseFormProps) {
  const form = useForm<CourseFormValues>({
    resolver: zodResolver(courseSchema),
    defaultValues: defaultValues ?? EMPTY_COURSE_VALUES,
  });
  const {
    register,
    control,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isDirty },
  } = form;
  const values = useWatch({ control }) as CourseFormValues;
  const categories = useCourseCategories();

  const categoryItems = (() => {
    const list = categories.data ?? [];
    const all = values.category && !list.includes(values.category) ? [values.category, ...list] : list;
    return all.map((c) => ({ value: c, label: c }));
  })();

  const isFree = values.accessModel === "free";
  const shortLength = values.shortDescription?.length ?? 0;

  const submit = handleSubmit(async (data) => {
    const ok = await onSubmit(formValuesToInput(data));
    if (ok && mode === "edit") reset(data);
  });

  const formCard = (
    <Card>
      <CardHeader>
        <CardTitle>Course details</CardTitle>
        <CardDescription>What students see in the catalog and how they get access.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <FormField id="course-name" label="Course name" error={errors.name?.message} required>
          <Input
            id="course-name"
            placeholder="e.g. Applied Data Analysis"
            aria-invalid={!!errors.name}
            aria-describedby={fieldDescribedBy("course-name", errors.name)}
            {...register("name")}
          />
        </FormField>

        <FormField
          id="course-short"
          label="Short description"
          error={errors.shortDescription?.message}
          required
          labelAction={
            <span
              className={cn(
                "text-xs tabular-nums",
                shortLength > SHORT_DESCRIPTION_MAX ? "text-destructive" : "text-muted-foreground",
              )}
              aria-live="polite"
            >
              {shortLength}/{SHORT_DESCRIPTION_MAX}
            </span>
          }
          description="Shown on course cards in the catalog."
        >
          <Input
            id="course-short"
            placeholder="One sentence that sells the course"
            aria-invalid={!!errors.shortDescription}
            aria-describedby={fieldDescribedBy("course-short", errors.shortDescription, true)}
            {...register("shortDescription")}
          />
        </FormField>

        <FormField id="course-description" label="Description" error={errors.description?.message} required>
          <Textarea
            id="course-description"
            rows={6}
            placeholder="What will students learn? Who is it for?"
            aria-invalid={!!errors.description}
            aria-describedby={fieldDescribedBy("course-description", errors.description)}
            {...register("description")}
          />
        </FormField>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField id="course-category" label="Category" error={errors.category?.message} required>
            <Controller
              control={control}
              name="category"
              render={({ field }) => (
                <Select
                  items={categoryItems}
                  value={field.value || null}
                  onValueChange={(v) => field.onChange(v ?? "")}
                  disabled={categories.isLoading}
                >
                  <SelectTrigger
                    id="course-category"
                    className="w-full"
                    onBlur={field.onBlur}
                    aria-invalid={!!errors.category}
                    aria-describedby={fieldDescribedBy("course-category", errors.category)}
                  >
                    <SelectValue placeholder={categories.isLoading ? "Loading categories…" : "Select a category"} />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryItems.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>

          <FormField id="course-status" label="Status" error={errors.status?.message} required>
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <Select items={STATUS_OPTIONS} value={field.value} onValueChange={(v) => v && field.onChange(v)}>
                  <SelectTrigger id="course-status" className="w-full" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
        </div>

        <div className="space-y-2">
          <p id="course-access-label" className="text-sm font-medium">
            Access model
            <span className="text-destructive" aria-hidden>
              *
            </span>
          </p>
          <Controller
            control={control}
            name="accessModel"
            render={({ field }) => (
              <RadioGroup
                aria-labelledby="course-access-label"
                value={field.value}
                onValueChange={(v) => {
                  const next = v as AccessModel;
                  field.onChange(next);
                  if (next === "free") setValue("price", 0, { shouldValidate: true, shouldDirty: true });
                }}
                className="grid gap-2 sm:grid-cols-3"
              >
                {ACCESS_MODEL_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/40 has-data-checked:border-primary has-data-checked:bg-primary/5"
                  >
                    <RadioGroupItem value={opt.value} className="mt-0.5" aria-describedby={`access-${opt.value}-help`} />
                    <span className="space-y-0.5">
                      <span className="block text-sm font-medium">{opt.title}</span>
                      <span id={`access-${opt.value}-help`} className="block text-xs text-muted-foreground">
                        {opt.help}
                      </span>
                    </span>
                  </label>
                ))}
              </RadioGroup>
            )}
          />
          {errors.accessModel && (
            <p role="alert" className="text-xs font-medium text-destructive">
              {errors.accessModel.message}
            </p>
          )}
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            id="course-price"
            label="Price (USD)"
            error={errors.price?.message}
            required={values.accessModel === "paid"}
            description={isFree ? "Free courses are always $0." : "Charged once per enrollment."}
          >
            <div className="relative">
              <span
                className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-sm text-muted-foreground"
                aria-hidden
              >
                $
              </span>
              <Input
                id="course-price"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                readOnly={isFree}
                aria-readonly={isFree}
                className={cn("pl-6 tabular-nums", isFree && "cursor-not-allowed bg-muted/50 text-muted-foreground")}
                aria-invalid={!!errors.price}
                aria-describedby={fieldDescribedBy("course-price", errors.price, true)}
                {...register("price", { valueAsNumber: true })}
              />
            </div>
          </FormField>

          <FormField
            id="course-duration"
            label="Access duration"
            error={errors.accessDuration?.message}
            required
            description="How long students keep access after it's granted."
          >
            <Controller
              control={control}
              name="accessDuration"
              render={({ field }) => {
                const items = durationItems(field.value);
                return (
                  <Select items={items} value={field.value} onValueChange={(v) => v && field.onChange(v)}>
                    <SelectTrigger
                      id="course-duration"
                      className="w-full"
                      onBlur={field.onBlur}
                      aria-describedby={fieldDescribedBy("course-duration", errors.accessDuration, true)}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {items.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                );
              }}
            />
          </FormField>
        </div>
      </CardContent>
      <CardFooter className="flex flex-col-reverse gap-2 border-t sm:flex-row sm:justify-end">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isPending || (mode === "edit" && !isDirty)}>
          {isPending && <Loader2 className="animate-spin" />}
          {mode === "create" ? "Create course" : "Save changes"}
        </Button>
      </CardFooter>
    </Card>
  );

  return (
    <form onSubmit={submit} noValidate>
      {renderAside ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
          {formCard}
          <div className="lg:sticky lg:top-20">{renderAside(values)}</div>
        </div>
      ) : (
        formCard
      )}
    </form>
  );
}
