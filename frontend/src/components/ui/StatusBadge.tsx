"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Coffee,
  MinusCircle,
  XCircle,
} from "lucide-react";

const STATUS_CONFIG: Record<
  string,
  { label: string; classes: string; Icon: typeof CheckCircle2 }
> = {
  present: {
    label: "Present",
    classes: "bg-emerald-50 text-emerald-900 border-emerald-200",
    Icon: CheckCircle2,
  },
  on_time: {
    label: "On Time",
    classes: "bg-emerald-50 text-emerald-900 border-emerald-200",
    Icon: CheckCircle2,
  },
  late: {
    label: "Late",
    classes: "bg-amber-50 text-amber-900 border-amber-300",
    Icon: Clock,
  },
  early_departure: {
    label: "Early Departure",
    classes: "bg-orange-50 text-orange-900 border-orange-200",
    Icon: AlertTriangle,
  },
  absent: {
    label: "Absent",
    classes: "bg-red-50 text-red-900 border-red-200",
    Icon: XCircle,
  },
  incomplete: {
    label: "Incomplete",
    classes: "bg-red-50 text-red-900 border-red-200",
    Icon: AlertTriangle,
  },
  on_leave: {
    label: "On Leave",
    classes: "bg-slate-100 text-slate-800 border-slate-300",
    Icon: MinusCircle,
  },
  overtime: {
    label: "Overtime",
    classes: "bg-[#FFD400]/25 text-[#0F3D3E] border-[#FFD400]",
    Icon: Clock,
  },
  on_break: {
    label: "On Break",
    classes: "bg-[#EAE5DC] text-[#0F3D3E] border-[#C9C0B1]",
    Icon: Coffee,
  },
  active: {
    label: "Active",
    classes: "bg-emerald-50 text-emerald-900 border-emerald-200",
    Icon: CheckCircle2,
  },
  suspended: {
    label: "Suspended",
    classes: "bg-red-50 text-red-900 border-red-200",
    Icon: XCircle,
  },
  inactive: {
    label: "Inactive",
    classes: "bg-slate-100 text-slate-700 border-slate-300",
    Icon: MinusCircle,
  },
  pending: {
    label: "Pending",
    classes: "bg-amber-50 text-amber-900 border-amber-300",
    Icon: Clock,
  },
  approved: {
    label: "Approved",
    classes: "bg-emerald-50 text-emerald-900 border-emerald-200",
    Icon: CheckCircle2,
  },
  rejected: {
    label: "Rejected",
    classes: "bg-red-50 text-red-900 border-red-200",
    Icon: XCircle,
  },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || {
    label: status.replace(/_/g, " "),
    classes: "bg-slate-100 text-slate-800 border-slate-300",
    Icon: MinusCircle,
  };
  const Icon = cfg.Icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.classes}`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{cfg.label}</span>
    </span>
  );
}
